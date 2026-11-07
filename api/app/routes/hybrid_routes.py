"""Routes : mode hybride."""
from __future__ import annotations

import asyncio, base64, io, json, time  # noqa: F401
from typing import AsyncIterator  # noqa: F401

import httpx  # noqa: F401
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import providers, hybrid
import logging

log = logging.getLogger("atom.hybrid_routes")

router = APIRouter()



class HybridIn(BaseModel):
    mode: str | None = Field(default=None, pattern="^(local|auto|mistral)$")
    allow_memory: bool | None = None
    allow_docs: bool | None = None
    allow_web: bool | None = None
    model: str | None = Field(default=None, max_length=80)
    provider: str | None = Field(default=None, max_length=40)


class ProviderModelIn(BaseModel):
    model: str = Field(max_length=120)


@router.put("/api/hybrid/providers/{pid}")
def put_provider(pid: str, body: ProviderModelIn):
    if not providers.get(pid):
        raise HTTPException(404, "Fournisseur inconnu")
    providers.set_model(pid, body.model)
    return hybrid.status()


@router.get("/api/hybrid")
def get_hybrid():
    return hybrid.status()


@router.get("/api/hybrid/models")
async def hybrid_models(provider: str | None = None):
    try:
        return {"models": await hybrid.list_models(provider)}
    except Exception as e:  # noqa: BLE001
        log.warning("hybrid_routes : erreur gérée", exc_info=True)
        raise HTTPException(502, f"Liste des modèles indisponible : {e}") from e


@router.put("/api/hybrid")
def put_hybrid(body: HybridIn):
    hybrid.save_settings({k: v for k, v in body.model_dump().items() if v is not None})
    return hybrid.status()
