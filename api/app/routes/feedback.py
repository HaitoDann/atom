"""Routes : avis sur les réponses."""
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



class FeedbackIn(BaseModel):
    value: int | None = Field(default=None, ge=-1, le=1)  # 1 = 👍, -1 = 👎, None = retirer
    reason: str | None = Field(default=None, max_length=500)


@router.patch("/api/messages/{mid}")
def feedback(mid: int, body: FeedbackIn):
    if not db.set_feedback(mid, body.value, body.reason):
        raise HTTPException(404, "Message introuvable")
    return {"ok": True}
