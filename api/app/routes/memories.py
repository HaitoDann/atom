"""Routes : souvenirs."""
from __future__ import annotations

import asyncio, base64, io, json, time  # noqa: F401
from typing import AsyncIterator  # noqa: F401

import httpx  # noqa: F401
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import db, llm, memory

router = APIRouter()


class MemoryIn(BaseModel):
    content: str = Field(min_length=1, max_length=500)



def _public(m: dict) -> dict:
    out = {k: m.get(k) for k in ("id", "content", "source", "created_at", "updated_at", "kind", "importance",
                                 "confidence", "review_at", "archived_at", "superseded_by", "hits", "last_used")}
    out["to_review"] = bool(m.get("review_at") and m["review_at"] < time.time())
    return out


@router.get("/api/memories")
def get_memories(archived: bool = False):
    return {"memories": [_public(m) for m in db.list_memories(active_only=not archived) if archived or not m.get("archived_at")],
            "archived": sum(1 for m in db.list_memories(active_only=False) if m.get("archived_at"))}


class MemoryMetaIn(BaseModel):
    kind: str | None = Field(default=None, pattern="^(semantique|procedurale|episodique)$")
    importance: int | None = Field(default=None, ge=1, le=3)
    confirm: bool | None = None     # « toujours vrai » : retire la date de révision
    restore: bool | None = None     # désarchiver


@router.post("/api/memories/{mid}/meta")
def memory_meta(mid: int, body: MemoryMetaIn):
    f = {}
    if body.kind:
        f["kind"] = body.kind
    if body.importance:
        f["importance"] = body.importance
    if body.confirm:
        f.update(review_at=None, confidence=1.0)
    if body.restore:
        f.update(archived_at=None, superseded_by=None)
    if f:
        db.set_memory_fields(mid, **f)
    return {"ok": True}


@router.post("/api/memories")
async def post_memory(body: MemoryIn):
    m = await memory.remember(body.content, source="manuel")
    if m is None:
        raise HTTPException(409, "Ce souvenir existe déjà.")
    return m   # action : added | merged (complète un souvenir) | replaced (contredit et remplace un ancien)


@router.patch("/api/memories/{mid}")
async def patch_memory(mid: int, body: MemoryIn):
    vec = await llm.embed([body.content.strip()])
    if not db.update_memory(mid, body.content.strip(), vec[0] if vec else None):
        raise HTTPException(404, "Souvenir introuvable")
    return {"ok": True}


@router.delete("/api/memories/{mid}")
def remove_memory(mid: int):
    if not db.delete_memory(mid):
        raise HTTPException(404, "Souvenir introuvable")
    return {"ok": True}


@router.delete("/api/memories")
def remove_all_memories():
    db.clear_memories()
    return {"ok": True}
