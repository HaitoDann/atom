"""Rappels : création depuis la conversation, planificateur, envoi.

Le modèle programme un rappel en insérant une commande dans sa réponse :
    [[rappel 2026-11-05T09:00 | appeler le garage]]
    [[annuler_rappel 12]]
Ces commandes sont retirées du texte avant affichage (voir CommandFilter).
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import db, notify
from .config import SCHEDULER_INTERVAL, TIMEZONE

log = logging.getLogger("atom.reminders")
TZ = ZoneInfo(TIMEZONE)

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]

CMD_RE = re.compile(r"\[\[\s*(rappel|annuler_rappel|recherche)\s+([^\]]*?)\s*\]\]", re.I)


def now_local() -> datetime:
    return datetime.now(TZ)


def human(ts: float) -> str:
    d = datetime.fromtimestamp(ts, TZ)
    today = now_local().date()
    if d.date() == today:
        day = "aujourd'hui"
    elif d.date() == today + timedelta(days=1):
        day = "demain"
    else:
        day = f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]}"
    return f"{day} à {d.hour:02d}h{d.minute:02d}"


def prompt_block() -> str:
    """Date courante, rappels en attente et mode d'emploi, pour le prompt système."""
    n = now_local()
    pending = db.list_reminders("pending", limit=15)
    lines = [
        f"Nous sommes le {JOURS[n.weekday()]} {n.day} {MOIS[n.month - 1]} {n.year}, "
        f"il est {n.hour:02d}h{n.minute:02d} ({n.strftime('%Y-%m-%dT%H:%M')}, fuseau {TIMEZONE}).",
        "",
        "Tu peux programmer des rappels : l'utilisateur recevra une notification sur son téléphone.",
        "Quand il te demande de lui rappeler quelque chose, ajoute À LA FIN de ta réponse :",
        "[[rappel AAAA-MM-JJTHH:MM | texte du rappel]]",
        "- Calcule la date à partir de la date actuelle ci-dessus. Sans heure précisée, choisis 09:00.",
        "- Le texte du rappel est court et s'adresse à l'utilisateur (ex. « Appeler le garage »).",
        "- Confirme en une phrase, avec le jour et l'heure. N'écris la commande que si on te le demande.",
        "Pour annuler un rappel : [[annuler_rappel ID]].",
    ]
    if pending:
        lines.append("\nRappels programmés :")
        lines += [f"- #{r['id']} {human(r['due_at'])} : {r['text']}" for r in pending]
    else:
        lines.append("\nAucun rappel programmé.")
    return "\n".join(lines)


def parse_due(raw: str) -> float | None:
    raw = raw.strip().replace(" ", "T", 1) if "T" not in raw else raw.strip()
    try:
        d = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=TZ)
    return d.timestamp()


def execute(cmd: str, arg: str, conversation_id: int | None) -> dict:
    """Exécute une commande extraite de la réponse. Renvoie un événement pour l'interface."""
    cmd = cmd.lower()
    if cmd == "annuler_rappel":
        m = re.search(r"\d+", arg)
        if m and db.delete_reminder(int(m.group())):
            return {"type": "reminder", "action": "cancelled", "id": int(m.group())}
        return {"type": "reminder", "action": "error", "message": "Rappel introuvable."}

    when, _, text = arg.partition("|")
    text = text.strip().strip("«»\"' ") or "Rappel"
    due = parse_due(when)
    if due is None:
        return {"type": "reminder", "action": "error", "message": f"Date illisible : {when.strip()}"}
    if due < time.time() - 60:
        return {"type": "reminder", "action": "error",
                "message": f"La date {human(due)} est déjà passée : rappel non programmé."}
    rid = db.add_reminder(conversation_id, text[:300], due)
    log.info("rappel #%s programmé %s : %s", rid, human(due), text)
    return {"type": "reminder", "action": "created", "id": rid, "text": text, "due_at": due,
            "when": human(due)}


class CommandFilter:
    """Retire les commandes [[…]] d'un flux de texte, en retenant ce qui pourrait en être une."""

    def __init__(self) -> None:
        self.buf = ""
        self.commands: list[tuple[str, str]] = []

    def feed(self, tok: str) -> str:
        self.buf += tok
        out = ""
        while True:
            i = self.buf.find("[[")
            if i < 0:
                # Un "[" final peut être le début d'une commande : on le garde.
                if self.buf.endswith("["):
                    out += self.buf[:-1]
                    self.buf = "["
                else:
                    out += self.buf
                    self.buf = ""
                return out
            out += self.buf[:i]
            self.buf = self.buf[i:]
            j = self.buf.find("]]")
            if j < 0:
                if len(self.buf) > 400:  # ce n'était pas une commande
                    out += self.buf
                    self.buf = ""
                return out
            chunk = self.buf[: j + 2]
            self.buf = self.buf[j + 2:]
            m = CMD_RE.fullmatch(chunk)
            if m:
                self.commands.append((m.group(1), m.group(2)))
            else:
                out += chunk

    def flush(self) -> str:
        rest, self.buf = self.buf, ""
        return rest


# ---------------------------------------------------------------- planificateur et relances
# Un rappel envoyé attend une confirmation (« Fait ») : boutons Telegram, interface web.
# Sans réponse, Atom relance après FOLLOWUP_DEFAULTS["delay"] minutes, au plus « max » fois, jamais pendant
# les heures calmes. « +1 h » et « Demain » reprogramment le rappel (l'ancien est marqué « reporté »).

FOLLOWUP_DEFAULTS = {"enabled": True, "delay": 60, "max": 2, "quiet_start": "22:00", "quiet_end": "07:30"}


def followup_settings() -> dict:
    import json
    s = dict(FOLLOWUP_DEFAULTS)
    try:
        s.update({k: v for k, v in json.loads(db.kv_get("followups") or "{}").items() if k in FOLLOWUP_DEFAULTS})
    except ValueError:
        pass
    return s


def save_followup_settings(new: dict) -> dict:
    import json
    s = followup_settings()
    s.update({k: v for k, v in new.items() if k in FOLLOWUP_DEFAULTS and v is not None})
    s["delay"] = max(5, min(24 * 60, int(s["delay"])))
    s["max"] = max(0, min(5, int(s["max"])))
    for k in ("quiet_start", "quiet_end"):
        if not re.fullmatch(r"\d{1,2}:\d{2}", str(s[k])):
            s[k] = FOLLOWUP_DEFAULTS[k]
    db.kv_set("followups", json.dumps(s))
    return s


def quiet(now: datetime, s: dict) -> bool:
    """Heures calmes (ex. 22:00 → 07:30, à cheval sur minuit) : pas de relance."""
    def mins(t: str) -> int:
        h, m = (int(x) for x in t.split(":"))
        return h * 60 + m
    a, b, n = mins(s["quiet_start"]), mins(s["quiet_end"]), now.hour * 60 + now.minute
    return (a <= n < b) if a <= b else (n >= a or n < b)


def buttons(rid: int) -> list[list[tuple[str, str]]]:
    return [[("✅ Fait", f"rem:done:{rid}"), ("⏰ +1 h", f"rem:snooze:{rid}:60"), ("📅 Demain", f"rem:tomorrow:{rid}")]]


async def fire(r: dict) -> None:
    text = r["text"]
    cid = r["conversation_id"] if r["conversation_id"] and db.conversation_exists(r["conversation_id"]) else None
    ok = await notify.send("⏰ Rappel d'Atom", text, cid, tags="alarm_clock", buttons=buttons(r["id"]))
    db.mark_reminder(r["id"], "sent" if ok or not notify.enabled() else "failed")
    if cid:
        db.add_message(cid, "assistant", f"⏰ **Rappel** : {text}", "surprise")


def followups_due(now_ts: float, now_local_dt: datetime, s: dict) -> list[dict]:
    """Rappels envoyés, non confirmés, dont la prochaine relance est due."""
    if not s["enabled"] or s["max"] <= 0 or quiet(now_local_dt, s):
        return []
    out = []
    for r in db.unacked_reminders():
        if (r.get("nudges") or 0) >= s["max"]:
            continue
        since = r.get("last_nudge_at") or r.get("sent_at") or r["due_at"]
        if now_ts - since >= s["delay"] * 60 and now_ts - r["due_at"] < 2 * 86400:   # pas de relance après 2 jours
            out.append(r)
    return out


async def nudge(r: dict) -> None:
    n = (r.get("nudges") or 0) + 1
    late = human(r["due_at"])
    ok = await notify.send("🔁 Relance d'Atom", f"{r['text']}\n_(rappel de {late}, pas encore marqué comme fait)_",
                           r["conversation_id"], tags="repeat", buttons=buttons(r["id"]))
    db.nudge_reminder(r["id"])
    log.info("relance %d du rappel #%s (%s)", n, r["id"], "envoyée" if ok else "aucun canal")


def act(rid: int, action: str, minutes: int = 60) -> dict:
    """Fait / reporter de N minutes / demain 9 h. Renvoie {ok, message, new_id?}."""
    r = db.get_reminder(rid)
    if not r:
        return {"ok": False, "message": "Rappel introuvable."}
    if r.get("acked_at"):
        return {"ok": False, "message": "Ce rappel est déjà traité."}
    if action == "done":
        db.ack_reminder(rid, "done")
        return {"ok": True, "message": f"✅ Noté : « {r['text']} » est fait."}
    if action == "snooze":
        due = time.time() + max(5, min(7 * 24 * 60, minutes)) * 60
    elif action == "tomorrow":
        d = now_local() + timedelta(days=1)
        due = d.replace(hour=9, minute=0, second=0, microsecond=0).timestamp()
    else:
        return {"ok": False, "message": "Action inconnue."}
    new_id = db.add_reminder(r["conversation_id"], r["text"], due)
    if r["status"] == "pending":
        db.delete_reminder(rid)
    else:
        db.ack_reminder(rid, "snoozed")
    return {"ok": True, "message": f"⏰ Je te le rappelle {human(due)}.", "new_id": new_id}


async def scheduler() -> None:
    log.info("planificateur démarré (toutes les %ss, fuseau %s)", SCHEDULER_INTERVAL, TIMEZONE)
    while True:
        try:
            for r in db.due_reminders(time.time()):
                await fire(r)
            for r in followups_due(time.time(), now_local(), followup_settings()):
                await nudge(r)
        except Exception:
            log.exception("erreur du planificateur")
        await asyncio.sleep(SCHEDULER_INTERVAL)
