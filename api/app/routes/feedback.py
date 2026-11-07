"""Routes : avis sur les réponses."""
from __future__ import annotations


from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import db

router = APIRouter()



class FeedbackIn(BaseModel):
    value: int | None = Field(default=None, ge=-1, le=1)  # 1 = 👍, -1 = 👎, None = retirer
    reason: str | None = Field(default=None, max_length=500)


@router.patch("/api/messages/{mid}")
def feedback(mid: int, body: FeedbackIn):
    if not db.set_feedback(mid, body.value, body.reason):
        raise HTTPException(404, "Message introuvable")
    return {"ok": True}
