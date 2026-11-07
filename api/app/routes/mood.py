"""Routes : humeur."""
from __future__ import annotations

import asyncio, base64, io, json, time  # noqa: F401
from typing import AsyncIterator  # noqa: F401

import httpx  # noqa: F401
from fastapi import APIRouter

from .. import db

router = APIRouter()



@router.get("/api/mood")
def mood(hours: int = 24):
    return {"events": db.emotions_since(time.time() - hours * 3600), "now": time.time()}
