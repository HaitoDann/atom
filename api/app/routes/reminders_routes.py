"""Routes : rappels et notifications."""
from __future__ import annotations

import asyncio, base64, io, json, time  # noqa: F401
from typing import AsyncIterator  # noqa: F401

import httpx  # noqa: F401
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


@router.post("/api/notify/test")
async def notify_test():
    if not notify.enabled():
        raise HTTPException(400, "Aucun canal configuré (ntfy ou Telegram).")
    if not await notify.send("Atom", "Ceci est une notification de test. Tout fonctionne ✨", tags="sparkles"):
        raise HTTPException(502, "Échec de l'envoi : regarde les logs du conteneur atom.")
    return {"ok": True}
