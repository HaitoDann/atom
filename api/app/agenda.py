"""Agenda d'Atom : rendez-vous stockés dans sa base, récurrences, rappels avant l'heure, flux .ics.

- Création en langage naturel dans la discussion (commande [[rdv …]] insérée par le modèle), dans l'interface
  (Réglages → Données → Agenda) ou par l'API. Atom connaît les rendez-vous des 14 prochains jours : il peut dire
  si tu es libre.
- Récurrence simple : quotidienne, hebdomadaire, mensuelle, annuelle, tous les N, jusqu'à une date ; une
  occurrence peut être supprimée seule.
- Rappel N minutes avant chaque occurrence (Telegram, ntfy), 30 min par défaut.
- Flux d'abonnement .ics protégé par un jeton (/agenda/<jeton>.ics) : le téléphone l'affiche dans son agenda
  (Android : appli ICSx⁵ ; lecture seule), en passant par Tailscale.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import secrets
import time
import uuid
from calendar import monthrange
from datetime import date, datetime, timedelta

from . import db, notify
from .config import TIMEZONE
from .reminders import JOURS, MOIS, TZ, now_local

log = logging.getLogger("atom.agenda")

REPEATS = ("", "daily", "weekly", "monthly", "yearly")
REPEAT_FR = {"": "", "daily": "chaque jour", "weekly": "chaque semaine", "monthly": "chaque mois", "yearly": "chaque année"}
DEFAULT_REMIND = 30


# ---------------------------------------------------------------- stockage

def _row(r) -> dict:
    d = dict(r)
    d["exdates"] = json.loads(d.get("exdates") or "[]")
    return d


def get(eid: int) -> dict | None:
    with db.conn() as c:
        r = c.execute("SELECT * FROM events WHERE id = ?", (eid,)).fetchone()
    return _row(r) if r else None


def all_events() -> list[dict]:
    with db.conn() as c:
        return [_row(r) for r in c.execute("SELECT * FROM events ORDER BY start_at").fetchall()]


def create(title: str, start_at: float, end_at: float | None = None, all_day: bool = False, location: str = "",
           notes: str = "", repeat: str = "", repeat_interval: int = 1, repeat_until: float | None = None,
           remind_min: int | None = DEFAULT_REMIND, conversation_id: int | None = None) -> dict:
    title = (title or "").strip()[:200] or "Rendez-vous"
    if repeat not in REPEATS:
        raise ValueError("récurrence inconnue")
    if all_day:
        d = datetime.fromtimestamp(start_at, TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        start_at = d.timestamp()
        end_at = max(end_at or 0, (d + timedelta(days=1)).timestamp())
    end_at = end_at if end_at and end_at > start_at else start_at + 3600
    now = time.time()
    with db.conn() as c:
        eid = c.execute(
            "INSERT INTO events (uid, title, start_at, end_at, all_day, location, notes, repeat, repeat_interval, "
            "repeat_until, remind_min, conversation_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"{uuid.uuid4()}@atom", title, start_at, end_at, int(all_day), location.strip()[:200], notes.strip()[:2000],
             repeat, max(1, min(99, int(repeat_interval or 1))), repeat_until, remind_min, conversation_id, now, now),
        ).lastrowid
    log.info("rendez-vous #%s : %s (%s)", eid, title, human_range(start_at, end_at, all_day))
    return get(eid)


FIELDS = ("title", "start_at", "end_at", "all_day", "location", "notes", "repeat", "repeat_interval", "repeat_until", "remind_min")


def update(eid: int, **f) -> dict | None:
    f = {k: v for k, v in f.items() if k in FIELDS}
    if "repeat" in f and f["repeat"] not in REPEATS:
        raise ValueError("récurrence inconnue")
    if not f or not get(eid):
        return get(eid)
    f["updated_at"] = time.time()
    with db.conn() as c:
        c.execute(f"UPDATE events SET {', '.join(k + ' = ?' for k in f)} WHERE id = ?", (*f.values(), eid))
    return get(eid)


def delete(eid: int, occurrence: float | None = None) -> bool:
    """Supprime l'événement, ou seulement une occurrence d'un événement récurrent."""
    ev = get(eid)
    if not ev:
        return False
    if occurrence is not None and ev["repeat"]:
        ex = sorted(set(ev["exdates"] + [float(occurrence)]))
        with db.conn() as c:
            c.execute("UPDATE events SET exdates = ?, updated_at = ? WHERE id = ?", (json.dumps(ex), time.time(), eid))
        return True
    with db.conn() as c:
        return c.execute("DELETE FROM events WHERE id = ?", (eid,)).rowcount > 0


# ---------------------------------------------------------------- récurrences

def _add_months(d: datetime, n: int) -> datetime | None:
    y, m = divmod(d.month - 1 + n, 12)
    y, m = d.year + y, m + 1
    if d.day > monthrange(y, m)[1]:
        return None                       # le 31 d'un mois qui n'en a pas : occurrence sautée (comme RFC 5545)
    return d.replace(year=y, month=m)


def occurrences(ev: dict, start: float, end: float, limit: int = 500) -> list[tuple[float, float]]:
    """Occurrences [(début, fin)] qui chevauchent [start, end[, en heure locale (les changements d'heure sont respectés)."""
    dur = ev["end_at"] - ev["start_at"]
    first = datetime.fromtimestamp(ev["start_at"], TZ)
    ex = {round(x) for x in ev.get("exdates") or []}
    until = ev.get("repeat_until")
    out, n, step = [], 0, max(1, ev.get("repeat_interval") or 1)
    while len(out) < limit and n < 20000:
        if not ev["repeat"]:
            d = first if n == 0 else None
        elif ev["repeat"] == "daily":
            d = first + timedelta(days=n * step)
        elif ev["repeat"] == "weekly":
            d = first + timedelta(weeks=n * step)
        elif ev["repeat"] == "monthly":
            d = _add_months(first, n * step)
        else:
            d = _add_months(first, 12 * n * step)
        if d is None and not ev["repeat"]:
            break
        n += 1
        if d is None:
            continue
        s = d.timestamp()          # heure locale conservée : le décalage d'été / d'hiver est recalculé par ZoneInfo
        if (until and s > until) or s >= end:
            break
        if s + dur > start and round(s) not in ex:
            out.append((s, s + dur))
        if not ev["repeat"]:
            break
    return out


def between(start: float, end: float) -> list[dict]:
    """Toutes les occurrences de la période, triées : {id, title, start, end, all_day, location, repeat…}."""
    out = []
    for ev in all_events():
        for s, e in occurrences(ev, start, end):
            out.append({**{k: ev[k] for k in ("id", "uid", "title", "all_day", "location", "notes", "repeat",
                                              "repeat_interval", "remind_min")}, "start": s, "end": e,
                        "when": human_range(s, e, bool(ev["all_day"]))})
    out.sort(key=lambda x: x["start"])
    return out


def day_bounds(d: date) -> tuple[float, float]:
    s = datetime(d.year, d.month, d.day, tzinfo=TZ)
    return s.timestamp(), (s + timedelta(days=1)).timestamp()


# ---------------------------------------------------------------- libellés

def _day(d: datetime) -> str:
    today = now_local().date()
    if d.date() == today:
        return "aujourd'hui"
    if d.date() == today + timedelta(days=1):
        return "demain"
    return f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]}"


def human_range(s: float, e: float, all_day: bool = False) -> str:
    a, b = datetime.fromtimestamp(s, TZ), datetime.fromtimestamp(e, TZ)
    if all_day:
        return _day(a) + " (toute la journée)"
    if a.date() == b.date():
        return f"{_day(a)} de {a:%Hh%M} à {b:%Hh%M}"
    return f"{_day(a)} {a:%Hh%M} → {_day(b)} {b:%Hh%M}"


def parse_when(raw: str) -> tuple[float, bool] | None:
    """« 2026-11-12T14:30 » ou « 2026-11-12 » (journée entière) → (timestamp, journée entière)."""
    raw = (raw or "").strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            return datetime.fromisoformat(raw).replace(tzinfo=TZ).timestamp(), True
        d = datetime.fromisoformat(raw.replace(" ", "T", 1))
    except ValueError:
        return None
    return (d if d.tzinfo else d.replace(tzinfo=TZ)).timestamp(), False


def parse_duration(raw: str) -> int | None:
    """« 1h30 », « 45 min », « 2 h », « 90 » → minutes."""
    raw = (raw or "").lower().replace(" ", "")
    m = re.fullmatch(r"(?:(\d+)h)?(\d+)?(?:min|m)?", raw)
    if not raw or not m or not (m.group(1) or m.group(2)):
        return None
    h = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    return h * 60 + mins if m.group(1) else mins


# ---------------------------------------------------------------- discussion

def prompt_block() -> str:
    now = time.time()
    upcoming = between(now - 3600, now + 14 * 86400)[:30]
    lines = ["Agenda de l'utilisateur (tu le gères) — 14 prochains jours :"]
    lines += [f"- #{x['id']} {x['when']} : {x['title']}" + (f" ({x['location']})" if x["location"] else "")
              + (f" [{REPEAT_FR[x['repeat']]}]" if x["repeat"] else "") for x in upcoming] or ["- (rien de prévu)"]
    lines += [
        "Pour AJOUTER un rendez-vous quand il te le demande, ajoute À LA FIN de ta réponse :",
        "[[rdv AAAA-MM-JJTHH:MM | durée | titre | lieu | récurrence]]",
        "- durée : « 1h », « 30min », « 1h30 » ; pour une journée entière, date seule AAAA-MM-JJ et durée vide.",
        "- lieu et récurrence sont facultatifs ; récurrence : chaque jour, chaque semaine, chaque mois, chaque année.",
        "- Sans durée précisée : 1h. Calcule la date à partir de la date actuelle. Confirme en une phrase.",
        "Pour SUPPRIMER : [[annuler_rdv ID]]. Pour savoir s'il est libre, réponds à partir de l'agenda ci-dessus.",
    ]
    return "\n".join(lines)


REPEAT_WORDS = {"jour": "daily", "quotidien": "daily", "semaine": "weekly", "hebdo": "weekly", "mois": "monthly",
                "mensuel": "monthly", "an": "yearly", "année": "yearly", "annuel": "yearly"}


def execute(cmd: str, arg: str, conversation_id: int | None) -> dict:
    """Commandes [[rdv …]] et [[annuler_rdv ID]] insérées par le modèle."""
    if cmd.lower() == "annuler_rdv":
        m = re.search(r"\d+", arg)
        ev = get(int(m.group())) if m else None
        if ev and delete(ev["id"]):
            return {"type": "agenda", "action": "cancelled", "id": ev["id"], "title": ev["title"]}
        return {"type": "agenda", "action": "error", "message": "Rendez-vous introuvable."}
    parts = [p.strip() for p in arg.split("|")] + [""] * 5
    when = parse_when(parts[0])
    if not when:
        return {"type": "agenda", "action": "error", "message": f"Date illisible : {parts[0]}"}
    start, all_day = when
    if not all_day and start < time.time() - 3600:
        return {"type": "agenda", "action": "error", "message": "Cette date est déjà passée : rendez-vous non ajouté."}
    mins = parse_duration(parts[1]) or 60
    rep = next((v for k, v in REPEAT_WORDS.items() if k in parts[4].lower()), "")
    ev = create(parts[2] or "Rendez-vous", start, start + mins * 60, all_day, parts[3], repeat=rep,
                conversation_id=conversation_id)
    return {"type": "agenda", "action": "created", "id": ev["id"], "title": ev["title"],
            "when": human_range(ev["start_at"], ev["end_at"], bool(ev["all_day"])) + (f", {REPEAT_FR[rep]}" if rep else "")}


def today_text() -> str:
    s, e = day_bounds(now_local().date())
    rows = between(s, e)
    return "\n".join(f"- {x['when'].replace("aujourd'hui de ", '').replace("aujourd'hui ", '')} : {x['title']}"
                     + (f" ({x['location']})" if x["location"] else "") for x in rows)


# ---------------------------------------------------------------- rappels avant l'heure

async def remind_due(now: float | None = None) -> int:
    """Envoie les rappels des occurrences qui commencent dans remind_min minutes (une seule fois chacune)."""
    now = now or time.time()
    sent = set(json.loads(db.kv_get("agenda_reminded") or "[]"))
    n = 0
    for x in between(now, now + 24 * 3600):
        if x["remind_min"] is None or x["all_day"]:
            continue
        key = f"{x['uid']}@{int(x['start'])}"
        if key in sent or x["start"] - x["remind_min"] * 60 > now:
            continue
        sent.add(key)
        mins = max(0, round((x["start"] - now) / 60))
        when = f"dans {mins} min" if mins else "maintenant"
        await notify.send(f"📅 {x['title']}", f"{when} ({x['when']})" + (f"\n📍 {x['location']}" if x["location"] else ""),
                          tags="calendar")
        n += 1
    keep = [k for k in sent if float(k.rsplit("@", 1)[1]) > now - 2 * 86400]     # on oublie les anciens
    db.kv_set("agenda_reminded", json.dumps(keep))
    return n


async def scheduler() -> None:
    while True:
        try:
            await remind_due()
        except Exception:
            log.exception("rappels de l'agenda")
        await asyncio.sleep(30)


# ---------------------------------------------------------------- flux .ics

def feed_token(regenerate: bool = False) -> str:
    t = db.kv_get("agenda_feed_token")
    if regenerate or not t:
        t = secrets.token_urlsafe(24)
        db.kv_set("agenda_feed_token", t)
    return t


def _esc(s: str) -> str:
    """Échappement des textes iCalendar (RFC 5545) : \\ ; , et retours à la ligne."""
    return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    out, b = [], line.encode()
    while len(b) > 75:
        cut = 75
        while cut and (b[cut] & 0xC0) == 0x80:      # ne coupe pas un caractère UTF-8
            cut -= 1
        out.append(b[:cut].decode())
        b = b" " + b[cut:]
    out.append(b.decode())
    return "\r\n".join(out)


def _local(ts: float) -> str:
    return datetime.fromtimestamp(ts, TZ).strftime("%Y%m%dT%H%M%S")


def ics() -> str:
    """Agenda complet au format iCalendar (RFC 5545), heures locales avec TZID."""
    L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Atom//Agenda//FR", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
         "X-WR-CALNAME:Atom", f"X-WR-TIMEZONE:{TIMEZONE}"]
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    for ev in all_events():
        L += ["BEGIN:VEVENT", f"UID:{ev['uid']}", f"DTSTAMP:{stamp}", f"SUMMARY:{_esc(ev['title'])}"]
        if ev["all_day"]:
            L += [f"DTSTART;VALUE=DATE:{_local(ev['start_at'])[:8]}", f"DTEND;VALUE=DATE:{_local(ev['end_at'])[:8]}"]
        else:
            L += [f"DTSTART;TZID={TIMEZONE}:{_local(ev['start_at'])}", f"DTEND;TZID={TIMEZONE}:{_local(ev['end_at'])}"]
        if ev["location"]:
            L.append(f"LOCATION:{_esc(ev['location'])}")
        if ev["notes"]:
            L.append(f"DESCRIPTION:{_esc(ev['notes'])}")
        if ev["repeat"]:
            r = f"RRULE:FREQ={ev['repeat'].upper()};INTERVAL={ev['repeat_interval']}"
            if ev["repeat_until"]:
                r += ";UNTIL=" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(ev["repeat_until"]))
            L.append(r)
            for x in ev["exdates"]:
                L.append(f"EXDATE;TZID={TIMEZONE}:{_local(x)}" if not ev["all_day"] else f"EXDATE;VALUE=DATE:{_local(x)[:8]}")
        if ev["remind_min"] is not None and not ev["all_day"]:
            L += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_esc(ev['title'])}",
                  f"TRIGGER:-PT{int(ev['remind_min'])}M", "END:VALARM"]
        L.append("END:VEVENT")
    L.append("END:VCALENDAR")
    return "\r\n".join(_fold(x) for x in L) + "\r\n"
