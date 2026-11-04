"""Atom — backend.

- Sert l'interface (web/index.html) sur la même origine.
- Relaie le modèle en streaming (NDJSON) vers le navigateur.
- Conversations multiples, mémoire automatique (faits + rappel sémantique).
- ATOM_PROVIDER=mock permet de tester toute la chaîne sans modèle.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import agent, db, llm, memory, notify, reminders, system, telegram
from .config import DEFAULT_MODEL, DEFAULT_PERSONA, EMBED_MODEL, PROVIDER, WEB_DIR

logging.basicConfig(level=logging.INFO)


def event(**kw) -> bytes:
    return (json.dumps(kw, ensure_ascii=False) + "\n").encode()


async def run_chat(*args) -> AsyncIterator[bytes]:
    async for ev in agent.chat_events(*args):
        yield event(**ev)


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_app: FastAPI):
    tasks = [asyncio.create_task(reminders.scheduler()), asyncio.create_task(telegram.run())]
    yield
    for t in tasks:
        t.cancel()


db.init()
app = FastAPI(title="Atom", lifespan=lifespan)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: int | None = None
    model: str | None = None
    persona: str | None = None
    auto_memory: bool = True


class MemoryIn(BaseModel):
    content: str = Field(min_length=1, max_length=500)


class ConvPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    pinned: bool | None = None


class TruncateIn(BaseModel):
    from_id: int


@app.get("/api/health")
async def health():
    if PROVIDER == "mock":
        return {"ok": True, "provider": PROVIDER, "ollama": True, "model_ready": True,
                "embeddings": True, "telegram": telegram.enabled(), "default_model": DEFAULT_MODEL}
    try:
        names = await llm.installed_models()
        ollama_ok = True
    except (httpx.HTTPError, ValueError):
        names, ollama_ok = [], False
    has_embed = any(n.split(":")[0] == EMBED_MODEL.split(":")[0] for n in names)
    return {
        "ok": True,
        "provider": PROVIDER,
        "ollama": ollama_ok,
        "model_ready": any(n.split(":")[0] != EMBED_MODEL.split(":")[0] for n in names),
        "embeddings": has_embed,
        "telegram": telegram.enabled(),
        "default_model": DEFAULT_MODEL,
    }


@app.get("/api/models")
async def models():
    if PROVIDER == "mock":
        return {"models": ["mock"], "default": "mock"}
    try:
        names = await llm.installed_models()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Ollama injoignable : {e}") from e
    # Le modèle d'embedding ne sait pas discuter : on le masque.
    chat_models = [n for n in names if n.split(":")[0] != EMBED_MODEL.split(":")[0]]
    return {"models": chat_models, "default": DEFAULT_MODEL}


@app.post("/api/chat")
async def chat(body: ChatIn):
    # Mémorisés pour que Telegram parle avec la même personnalité et le même modèle.
    if body.persona:
        db.kv_set("persona", body.persona)
    if body.model:
        db.kv_set("model", body.model)
    return StreamingResponse(
        run_chat(
            body.message.strip(),
            body.conversation_id,
            body.model or DEFAULT_MODEL,
            body.persona or DEFAULT_PERSONA,
            body.auto_memory,
        ),
        media_type="application/x-ndjson",
    )


# ---- conversations


@app.get("/api/conversations")
def get_conversations():
    return {"conversations": db.list_conversations()}


@app.get("/api/conversations/{cid}/messages")
def get_messages(cid: int):
    if not db.conversation_exists(cid):
        raise HTTPException(404, "Conversation introuvable")
    return {"messages": db.messages(cid, 1000)}


@app.patch("/api/conversations/{cid}")
def patch_conversation(cid: int, body: ConvPatch):
    if body.title:
        db.rename_conversation(cid, body.title.strip())
    if body.pinned is not None:
        db.pin_conversation(cid, body.pinned)
    return {"ok": True}


@app.post("/api/conversations/{cid}/truncate")
def truncate(cid: int, body: TruncateIn):
    """Supprime les messages à partir d'un message (pour modifier ou régénérer)."""
    return {"deleted": db.truncate_conversation(cid, body.from_id)}


@app.get("/api/search")
def search(q: str):
    q = q.strip()
    return {"results": db.search(q) if len(q) >= 2 else []}


@app.get("/api/system")
async def system_info():
    return await system.snapshot()


@app.delete("/api/conversations/{cid}")
def remove_conversation(cid: int):
    db.delete_conversation(cid)
    return {"ok": True}


# ---- souvenirs


def _public(m: dict) -> dict:
    return {k: m[k] for k in ("id", "content", "source", "created_at", "updated_at")}


@app.get("/api/memories")
def get_memories():
    return {"memories": [_public(m) for m in db.list_memories()]}


@app.post("/api/memories")
async def post_memory(body: MemoryIn):
    m = await memory.remember(body.content, source="manuel")
    if m is None:
        raise HTTPException(409, "Ce souvenir existe déjà.")
    return m


@app.patch("/api/memories/{mid}")
async def patch_memory(mid: int, body: MemoryIn):
    vec = await llm.embed([body.content.strip()])
    if not db.update_memory(mid, body.content.strip(), vec[0] if vec else None):
        raise HTTPException(404, "Souvenir introuvable")
    return {"ok": True}


@app.delete("/api/memories/{mid}")
def remove_memory(mid: int):
    if not db.delete_memory(mid):
        raise HTTPException(404, "Souvenir introuvable")
    return {"ok": True}


@app.delete("/api/memories")
def remove_all_memories():
    db.clear_memories()
    return {"ok": True}


# ---- rappels et notifications


class ReminderIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    due: str  # "AAAA-MM-JJTHH:MM", heure locale


def _reminder_out(r: dict) -> dict:
    return {**r, "when": reminders.human(r["due_at"])}


@app.get("/api/reminders")
def get_reminders(status: str = "pending"):
    rows = db.list_reminders(None if status == "all" else status)
    return {"reminders": [_reminder_out(r) for r in rows], "notifications": notify.enabled()}


@app.post("/api/reminders")
def post_reminder(body: ReminderIn):
    ev = reminders.execute("rappel", f"{body.due} | {body.text}", None)
    if ev["action"] != "created":
        raise HTTPException(400, ev["message"])
    return ev


@app.delete("/api/reminders/{rid}")
def remove_reminder(rid: int):
    if not db.delete_reminder(rid):
        raise HTTPException(404, "Rappel introuvable ou déjà envoyé")
    return {"ok": True}


@app.post("/api/notify/test")
async def notify_test():
    if not notify.enabled():
        raise HTTPException(400, "Aucun canal configuré (ntfy ou Telegram).")
    if not await notify.send("Atom", "Ceci est une notification de test. Tout fonctionne ✨", tags="sparkles"):
        raise HTTPException(502, "Échec de l'envoi : regarde les logs du conteneur atom.")
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")
