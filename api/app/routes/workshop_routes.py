"""Routes : atelier multi-IA."""
from __future__ import annotations

import asyncio, base64, io, json, time  # noqa: F401
from typing import AsyncIterator  # noqa: F401

import httpx  # noqa: F401
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .. import providers, workshop

router = APIRouter()


from ..streaming import event  # noqa: E402



class WorkshopIn(BaseModel):
    enabled: bool | None = None
    pattern: str | None = Field(default=None, pattern="^(review|panel|debate)$")
    participants: list[str] | None = Field(default=None, max_length=3)
    rounds: int | None = Field(default=None, ge=1, le=3)


class WorkshopRunIn(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: int | None = None
    pattern: str | None = Field(default=None, pattern="^(review|panel|debate)$")
    participants: list[str] | None = Field(default=None, max_length=3)


@router.get("/api/workshop")
def get_workshop():
    s = workshop.settings()
    opts = [{"id": "auto", "label": "Automatique"}, {"id": "local", "label": workshop.engine_label("local")}]
    opts += [{"id": f"p:{p.id}", "label": workshop.engine_label(f"p:{p.id}"), "family": providers.family_of(providers.model_of(p), p.family),
              "strength": p.strength} for p in providers.ALL if p.configured]
    assigned = workshop.assign(s["pattern"], s["participants"])
    return {**s, "patterns": workshop.PATTERNS, "roles": workshop.ROLES, "options": opts,
            "assigned": [workshop.engine_label(x) for x in assigned], "warnings": workshop.warnings(s["pattern"], s["participants"])}


@router.put("/api/workshop")
def put_workshop(body: WorkshopIn):
    workshop.save_settings({k: v for k, v in body.model_dump().items() if v is not None})
    return get_workshop()


@router.post("/api/workshop/run")
async def run_workshop(body: WorkshopRunIn):
    if not workshop.settings()["enabled"]:
        raise HTTPException(400, "L'atelier est désactivé (Réglages → Atelier).")
    return StreamingResponse(
        (event(**ev) async for ev in workshop.run(body.message.strip(), body.conversation_id, body.pattern, body.participants)),
        media_type="application/x-ndjson")
