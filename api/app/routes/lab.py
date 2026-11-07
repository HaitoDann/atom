"""Routes : labo des modèles locaux."""
from __future__ import annotations

import asyncio, base64, io, json, time  # noqa: F401
from typing import AsyncIterator  # noqa: F401

import httpx  # noqa: F401
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .. import db, models_lab, providers, llm, system
from ..config import DEFAULT_MODEL, EMBED_MODEL, PROVIDER
from ..jobs import background

router = APIRouter()


from ..streaming import event  # noqa: E402
import logging  # noqa: E402

log = logging.getLogger("atom.lab")



class ModelName(BaseModel):
    name: str = Field(min_length=2, max_length=120, pattern=r"^[A-Za-z0-9._:/-]+$")


class CompareIn(BaseModel):
    models: list[str] = Field(min_length=1, max_length=4)
    prompts: list[str] = Field(default_factory=list, max_length=4)   # ids de PROMPTS
    custom: str = Field(default="", max_length=2000)


@router.get("/api/lab")
async def lab():
    try:
        installed = [] if PROVIDER == "mock" else await llm.installed_models()
    except httpx.HTTPError:
        installed = []
    if PROVIDER == "mock":
        installed = ["mock", "qwen3:4b-instruct-2507-q4_K_M"]
    snap = await system.snapshot()
    return {"installed": [n for n in installed if n.split(":")[0] != EMBED_MODEL.split(":")[0]],
            "suggested": models_lab.SUGGESTED, "prompts": [{"id": p["id"], "label": p["label"]} for p in models_lab.PROMPTS],
            "pulls": models_lab.pulls(), "memory": snap.get("memory"), "current": db.kv_get("model") or DEFAULT_MODEL,
            "remote": [{"id": f"p:{p.id}", "name": p.name, "model": providers.model_of(p), "left": providers.quota_left(p.id)}
                       for p in providers.ALL if p.configured]}


@router.post("/api/lab/install")
async def lab_install(body: ModelName):
    st = next((p for p in models_lab.pulls() if p["name"] == body.name), None)
    if st and not st["done"]:
        raise HTTPException(409, "Installation déjà en cours")
    background(models_lab.install(body.name))
    return {"ok": True}


@router.post("/api/lab/delete")
async def lab_delete(body: ModelName):
    if body.name == (db.kv_get("model") or DEFAULT_MODEL):
        raise HTTPException(409, "C'est le modèle utilisé par Atom : choisis-en un autre avant de le supprimer.")
    try:
        await models_lab.delete(body.name)
    except Exception as e:  # noqa: BLE001
        log.warning("lab : erreur gérée", exc_info=True)
        raise HTTPException(502, str(e)) from e
    return {"ok": True}


@router.post("/api/lab/compare")
async def lab_compare(body: CompareIn):
    prompts = [p for p in models_lab.PROMPTS if p["id"] in body.prompts]
    if body.custom.strip():
        prompts.append({"id": "perso", "label": "Ta question", "text": body.custom.strip()})
    if not prompts:
        raise HTTPException(422, "Choisis au moins une question")
    keep = db.kv_get("model") or DEFAULT_MODEL
    return StreamingResponse((event(**ev) async for ev in models_lab.compare(body.models, prompts, keep)),
                             media_type="application/x-ndjson")


@router.post("/api/benchmark")
async def benchmark(model: str | None = None):
    """Génère un court texte et renvoie la vitesse mesurée par Ollama."""
    m = model or db.kv_get("model") or DEFAULT_MODEL
    t0 = time.time()
    n = 0
    try:
        async for _ in llm.stream_chat(m, [{"role": "user", "content": "Écris une phrase de 40 mots sur la mer. /no_think"}]):
            n += 1
    except Exception as e:  # noqa: BLE001
        log.warning("lab : erreur gérée", exc_info=True)
        raise HTTPException(502, str(e)) from e
    return {"model": m, "wall_s": round(time.time() - t0, 2), **llm.last_stats}
