"""Routes : rappels et notifications."""
from __future__ import annotations


from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import db, notify, reminders

router = APIRouter()



class ReminderIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    due: str  # "AAAA-MM-JJTHH:MM", heure locale


def _reminder_out(r: dict) -> dict:
    return {**r, "when": reminders.human(r["due_at"])}


@router.get("/api/reminders")
def get_reminders(status: str = "pending"):
    rows = db.list_reminders(None if status == "all" else status)
    return {"reminders": [_reminder_out(r) for r in rows], "notifications": notify.enabled()}


@router.post("/api/reminders")
def post_reminder(body: ReminderIn):
    ev = reminders.execute("rappel", f"{body.due} | {body.text}", None)
    if ev["action"] != "created":
        raise HTTPException(400, ev["message"])
    return ev


@router.delete("/api/reminders/{rid}")
def remove_reminder(rid: int):
    if not db.delete_reminder(rid):
        raise HTTPException(404, "Rappel introuvable ou déjà envoyé")
    return {"ok": True}


class SnoozeIn(BaseModel):
    minutes: int | None = Field(default=None, ge=5, le=7 * 24 * 60)
    tomorrow: bool = False


class FollowupsIn(BaseModel):
    enabled: bool | None = None
    delay: int | None = Field(default=None, ge=5, le=24 * 60)
    max: int | None = Field(default=None, ge=0, le=5)
    quiet_start: str | None = Field(default=None, pattern=r"^\d{1,2}:\d{2}$")
    quiet_end: str | None = Field(default=None, pattern=r"^\d{1,2}:\d{2}$")


@router.get("/api/reminders/unacked")
def unacked():
    """Rappels envoyés en attente de confirmation (relancés tant qu'ils ne sont pas « faits »)."""
    return {"reminders": [_reminder_out(r) for r in db.unacked_reminders()], "followups": reminders.followup_settings()}


@router.post("/api/reminders/{rid}/done")
def reminder_done(rid: int):
    res = reminders.act(rid, "done")
    if not res["ok"]:
        raise HTTPException(409, res["message"])
    return res


@router.post("/api/reminders/{rid}/snooze")
def reminder_snooze(rid: int, body: SnoozeIn):
    res = reminders.act(rid, "tomorrow" if body.tomorrow else "snooze", body.minutes or 60)
    if not res["ok"]:
        raise HTTPException(409, res["message"])
    return res


@router.put("/api/reminders/followups")
def put_followups(body: FollowupsIn):
    return reminders.save_followup_settings(body.model_dump(exclude_none=True))


@router.post("/api/notify/test")
async def notify_test():
    if not notify.enabled():
        raise HTTPException(400, "Aucun canal configuré (ntfy ou Telegram).")
    if not await notify.send("Atom", "Ceci est une notification de test. Tout fonctionne ✨", tags="sparkles"):
        raise HTTPException(502, "Échec de l'envoi : regarde les logs du conteneur atom.")
    return {"ok": True}
