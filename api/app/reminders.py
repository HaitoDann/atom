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


# ---------------------------------------------------------------- planificateur


async def fire(r: dict) -> None:
    text = r["text"]
    cid = r["conversation_id"] if r["conversation_id"] and db.conversation_exists(r["conversation_id"]) else None
    ok = await notify.send("⏰ Rappel d'Atom", text, cid, tags="alarm_clock")
    db.mark_reminder(r["id"], "sent" if ok or not notify.enabled() else "failed")
    if cid:
        db.add_message(cid, "assistant", f"⏰ **Rappel** : {text}", "surprise")


async def scheduler() -> None:
    log.info("planificateur démarré (toutes les %ss, fuseau %s)", SCHEDULER_INTERVAL, TIMEZONE)
    while True:
        try:
            for r in db.due_reminders(time.time()):
                await fire(r)
        except Exception:  # noqa: BLE001 — le planificateur ne doit jamais s'arrêter
            log.exception("erreur du planificateur")
        await asyncio.sleep(SCHEDULER_INTERVAL)
