"""Routes du canevas."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import canvas
import logging

log = logging.getLogger("atom.canvas")

router = APIRouter()


class CanvasIn(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    content: str | None = Field(default=None, max_length=400_000)
    conversation_id: int | None = None
    kind: str | None = Field(default=None, pattern="^(doc|code)$")


class CanvasEditIn(BaseModel):
    instruction: str = Field(min_length=2, max_length=2000)
    selection: str = Field(default="", max_length=100_000)
    engine: str = Field(default="auto", pattern="^(auto|local)$")


@router.get("/api/canvas")
def canvas_list(conversation_id: int | None = None):
    return {"canvases": canvas.list_for(conversation_id)}


@router.post("/api/canvas")
def canvas_create(body: CanvasIn):
    cid = canvas.create(body.title or "Sans titre", body.content or "", body.conversation_id, body.kind or "doc")
    return canvas.get(cid)


@router.get("/api/canvas/{cid}")
def canvas_get(cid: int):
    c = canvas.get(cid)
    if not c:
        raise HTTPException(404, "Canevas introuvable")
    return c


@router.put("/api/canvas/{cid}")
def canvas_put(cid: int, body: CanvasIn):
    try:
        cur = canvas.get(cid) or {}
        return canvas.save(cid, body.content if body.content is not None else cur.get("content", ""), "toi", "", body.title)
    except KeyError as e:
        raise HTTPException(404, "Canevas introuvable") from e


@router.post("/api/canvas/{cid}/edit")
async def canvas_edit(cid: int, body: CanvasEditIn):
    try:
        return await canvas.edit(cid, body.instruction, body.selection, body.engine)
    except KeyError as e:
        raise HTTPException(404, "Canevas introuvable") from e
    except Exception as e:
        log.warning("canvas : erreur gérée", exc_info=True)
        raise HTTPException(502, f"Modification impossible : {e}") from e


@router.get("/api/canvas/{cid}/versions/{i}")
def canvas_version(cid: int, i: int):
    try:
        return {"content": canvas.version(cid, i)}
    except KeyError as e:
        raise HTTPException(404, "Version introuvable") from e


@router.delete("/api/canvas/{cid}")
def canvas_delete(cid: int):
    canvas.delete(cid)
    return {"ok": True}
