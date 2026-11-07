"""Routes : conversations."""
from __future__ import annotations

import asyncio, base64, io, json, time  # noqa: F401
from typing import AsyncIterator  # noqa: F401

import httpx  # noqa: F401
from fastapi import APIRouter, HTTPException, Request  # noqa: F401
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse  # noqa: F401
from pydantic import BaseModel, Field  # noqa: F401

from .. import agent, agentcode, analysis, auth, backup, canvas, codeedit, proxmox, research, sandbox, spaces, db, gitops, models_lab, ocr, providers, hybrid, library, llm, memory, notify, reminders, search, system, telegram, workshop  # noqa: F401
from ..config import DEFAULT_MODEL, DEFAULT_PERSONA, EMBED_MODEL, PROVIDER, WEB_DIR  # noqa: F401
from ..jobs import background  # noqa: F401

router = APIRouter()


class ConvPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    pinned: bool | None = None


class TruncateIn(BaseModel):
    from_id: int



@router.get("/api/conversations")
def get_conversations():
    return {"conversations": db.list_conversations()}


@router.get("/api/conversations/{cid}/messages")
def get_messages(cid: int):
    if not db.conversation_exists(cid):
        raise HTTPException(404, "Conversation introuvable")
    return {"messages": db.messages(cid, 1000)}


@router.patch("/api/conversations/{cid}")
def patch_conversation(cid: int, body: ConvPatch):
    if body.title:
        db.rename_conversation(cid, body.title.strip())
    if body.pinned is not None:
        db.pin_conversation(cid, body.pinned)
    return {"ok": True}


@router.post("/api/conversations/{cid}/truncate")
def truncate(cid: int, body: TruncateIn):
    """Supprime les messages à partir d'un message (pour modifier ou régénérer)."""
    return {"deleted": db.truncate_conversation(cid, body.from_id)}


@router.get("/api/search")
def search_conversations(q: str):
    q = q.strip()
    return {"results": db.search(q) if len(q) >= 2 else []}


@router.get("/api/system")
async def system_info():
    return {**await system.snapshot(), "last": dict(llm.last_stats)}


@router.delete("/api/conversations/{cid}")
def remove_conversation(cid: int):
    db.delete_conversation(cid)
    return {"ok": True}
