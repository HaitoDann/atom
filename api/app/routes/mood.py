"""Routes : humeur."""
from __future__ import annotations

import time

from fastapi import APIRouter

from .. import db

router = APIRouter()



@router.get("/api/mood")
def mood(hours: int = 24):
    return {"events": db.emotions_since(time.time() - hours * 3600), "now": time.time()}
