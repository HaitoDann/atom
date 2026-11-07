"""Routes : surveillance Proxmox (lecture seule)."""
from __future__ import annotations

import asyncio, base64, io, json, time  # noqa: F401
from typing import AsyncIterator  # noqa: F401

import httpx  # noqa: F401
from fastapi import APIRouter
from pydantic import BaseModel, Field

from .. import proxmox

router = APIRouter()



class ProxmoxIn(BaseModel):
    cpu: int | None = Field(default=None, ge=50, le=100)
    mem: int | None = Field(default=None, ge=50, le=100)
    storage: int | None = Field(default=None, ge=50, le=100)
    minutes: int | None = Field(default=None, ge=1, le=120)
    notify: bool | None = None
    guest_down: bool | None = None


@router.get("/api/proxmox")
async def proxmox_state():
    if proxmox.configured() and time.time() - proxmox.state.get("updated", 0) > 50:
        await proxmox.poll()
    return {**proxmox.state, "configured": proxmox.configured(), "url": proxmox.URL, "alerts": proxmox.alerts(),
            "settings": proxmox.settings(),
            "history": {k: list(v)[-180:] for k, v in proxmox.history.items()}}


@router.put("/api/proxmox")
def proxmox_settings(body: ProxmoxIn):
    return {"settings": proxmox.save_settings({k: v for k, v in body.model_dump().items() if v is not None})}
