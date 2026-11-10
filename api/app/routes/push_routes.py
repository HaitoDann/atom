"""Routes : notifications Web Push (appli installée sur le téléphone) et actions des boutons de notification."""
from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import push

router = APIRouter()


class SubIn(BaseModel):
    subscription: dict
    device: str = Field(default="", max_length=120)


class UnsubIn(BaseModel):
    endpoint: str = Field(max_length=2000)


class ActionIn(BaseModel):
    action: str = Field(max_length=80)


@router.get("/api/push")
def push_state():
    return {"public_key": push.public_key(), "devices": [{"id": s["id"], "device": s["device"], "created_at": s["created_at"],
                                                          "last_ok": s["last_ok"]} for s in push.subscriptions()]}


@router.post("/api/push/subscribe")
def push_subscribe(body: SubIn, request: Request):
    try:
        return push.subscribe(body.subscription, body.device, request.headers.get("user-agent", "")[:120])
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/api/push/unsubscribe")
def push_unsubscribe(body: UnsubIn):
    return {"ok": push.unsubscribe(body.endpoint)}


@router.post("/api/push/test")
async def push_test():
    if not push.enabled():
        raise HTTPException(400, "Aucun appareil abonné.")
    ok = await push.send("Atom", "Les notifications fonctionnent sur cet appareil ✨", "/", "test")
    if not ok:
        raise HTTPException(502, "Envoi refusé par le service de notification : regarde les logs du conteneur atom.")
    return {"ok": True}


@router.post("/api/push/action")
def push_action(body: ActionIn):
    """Bouton touché sur une notification (Fait, +1 h, Demain, Garder, Oublier)."""
    from .. import memory_care, reminders
    m = re.fullmatch(r"rem:(done|snooze|tomorrow):(\d+)(?::(\d+))?", body.action)
    if m:
        return reminders.act(int(m.group(2)), m.group(1), int(m.group(3) or 60))
    m = re.fullmatch(r"mem:(keep|forget):(\d+)", body.action)
    if m:
        return memory_care.act(int(m.group(2)), m.group(1))
    raise HTTPException(400, "Action inconnue")
