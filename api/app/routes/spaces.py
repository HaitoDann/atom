"""Routes : espaces."""
from __future__ import annotations


from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import spaces

router = APIRouter()



class SpaceIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    instructions: str | None = Field(default=None, max_length=8000)
    collections: list[int] | None = Field(default=None, max_length=50)


@router.get("/api/spaces")
def get_spaces():
    return {"spaces": spaces.list_all()}


@router.post("/api/spaces")
def post_space(body: SpaceIn):
    if not body.name:
        raise HTTPException(422, "Nom manquant")
    sid = spaces.create(body.name, body.instructions or "", body.collections or [])
    return spaces.get(sid)


@router.patch("/api/spaces/{sid}")
def patch_space(sid: int, body: SpaceIn):
    if not spaces.get(sid):
        raise HTTPException(404, "Espace introuvable")
    spaces.update(sid, **{k: v for k, v in body.model_dump().items() if v is not None})
    return spaces.get(sid)


@router.delete("/api/spaces/{sid}")
def del_space(sid: int):
    spaces.delete(sid)
    return {"ok": True}


class ConvSpaceIn(BaseModel):
    space_id: int | None = None


@router.put("/api/conversations/{cid}/space")
def put_conv_space(cid: int, body: ConvSpaceIn):
    if body.space_id and not spaces.get(body.space_id):
        raise HTTPException(404, "Espace introuvable")
    spaces.assign(cid, body.space_id)
    return {"ok": True}
