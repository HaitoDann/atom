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
import re
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import db, llm, memory
from .config import (
    CONTEXT_TURNS,
    DEFAULT_MODEL,
    DEFAULT_PERSONA,
    EMBED_MODEL,
    EMOTIONS,
    OLLAMA_URL,
    PROVIDER,
    WEB_DIR,
)

logging.basicConfig(level=logging.INFO)
TAG_RE = re.compile(r"^\s*\[([a-zA-Z]+)\]\s*")
_background: set[asyncio.Task] = set()

# --------------------------------------------------------------------------
# Agent
# --------------------------------------------------------------------------


def system_prompt(persona: str, memory_block: str) -> str:
    s = (
        f"{persona.strip()}\n\n"
        "Tu possèdes un corps : une sphère de fragments lumineux qui exprime ton état.\n\n"
        "Longueur des réponses — adapte-toi à la demande :\n"
        "- Conversation, salutation, question simple : une à trois phrases, naturellement.\n"
        "- Demande de travail (explication, comparaison, tableau, liste, code, rédaction) : "
        "réponse complète et structurée en Markdown (titres courts, listes, tableaux, blocs de code).\n\n"
        "Commence TOUJOURS ta réponse par ton émotion entre crochets, puis ton message. "
        f"Émotions possibles : {', '.join(EMOTIONS)}.\n"
        "(talking = neutre, joy = content, sad = triste, angry = agacé, surprise = étonné, "
        "fear = inquiet, thinking = perplexe, sleep = fatigué, idle = calme)\n"
        "Exemple : [joy] Ravi de te revoir !\n"
        "Ne réfléchis pas à voix haute, ne décris pas ton raisonnement : réponds directement.\n"
        "/no_think"
    )
    if memory_block:
        s += "\n\n" + memory_block
    return s


def event(**kw) -> bytes:
    return (json.dumps(kw, ensure_ascii=False) + "\n").encode()


def make_title(text: str) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    return t if len(t) <= 48 else t[:46].rstrip() + "…"


async def run_chat(
    message: str, conversation_id: int | None, model: str, persona: str, auto_memory: bool
) -> AsyncIterator[bytes]:
    if conversation_id is None or not db.conversation_exists(conversation_id):
        conversation_id = db.create_conversation(make_title(message))
    elif not db.messages(conversation_id, 1):
        db.rename_conversation(conversation_id, make_title(message))
    yield event(type="meta", conversation_id=conversation_id)

    history = db.messages(conversation_id, CONTEXT_TURNS * 2)
    mem_block = await memory.context_for(message, conversation_id)
    msgs = [{"role": "system", "content": system_prompt(persona, mem_block)}]
    msgs += [{"role": m["role"], "content": m["content"]} for m in history]
    msgs.append({"role": "user", "content": message})
    db.add_message(conversation_id, "user", message)

    emotion: str | None = None
    head = ""  # tampon tant que le tag d'émotion n'est pas résolu
    text = ""
    try:
        async for tok in llm.stream_chat(model, msgs):
            if emotion is None:
                head += tok
                # Raisonnement interne (modèles "thinking") : on l'écarte.
                if "</think>" in head:
                    head = head.split("</think>")[-1]
                elif head.lstrip().startswith("<think>") or "<think>".startswith(head.lstrip()[:7] or "x"):
                    continue
                stripped = head.lstrip()
                if not stripped:
                    continue
                if stripped.startswith("[") and "]" not in stripped and len(stripped) < 20:
                    continue  # le tag arrive encore
                m = TAG_RE.match(stripped)
                if m and m.group(1).lower() in EMOTIONS:
                    emotion = m.group(1).lower()
                    tok = stripped[m.end():]
                else:
                    emotion = "talking"
                    tok = stripped
                yield event(type="emotion", emotion=emotion)
            if tok:
                text += tok
                yield event(type="token", text=tok)
        if emotion is None:  # réponse vide ou tag seul
            emotion = "talking"
            text = "" if head.lstrip().startswith("<think>") else TAG_RE.sub("", head).strip()
            if text:
                yield event(type="token", text=text)
        text = text.strip() or "…"
        db.add_message(conversation_id, "assistant", text, emotion)
        yield event(type="done", emotion=emotion)
    except Exception as e:  # noqa: BLE001 — on renvoie l'erreur à l'interface
        msg = str(e) or e.__class__.__name__
        if isinstance(e, httpx.ConnectError):
            msg = f"Impossible de joindre Ollama sur {OLLAMA_URL}."
        yield event(type="error", message=msg)
        return

    if not auto_memory:
        return
    # Mémorisation en tâche de fond : elle survit même si le navigateur se ferme.
    task = asyncio.create_task(memory.after_exchange(model, conversation_id, message, text))
    _background.add(task)
    task.add_done_callback(_background.discard)
    try:
        added = await asyncio.wait_for(asyncio.shield(task), timeout=120)
        if added:
            yield event(type="memory", added=added)
    except asyncio.TimeoutError:
        pass


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------

app = FastAPI(title="Atom")
db.init()


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: int | None = None
    model: str | None = None
    persona: str | None = None
    auto_memory: bool = True


class MemoryIn(BaseModel):
    content: str = Field(min_length=1, max_length=500)


class TitleIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)


@app.get("/api/health")
async def health():
    if PROVIDER == "mock":
        return {"ok": True, "provider": PROVIDER, "ollama": True, "model_ready": True,
                "embeddings": True, "default_model": DEFAULT_MODEL}
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
def patch_conversation(cid: int, body: TitleIn):
    db.rename_conversation(cid, body.title.strip())
    return {"ok": True}


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


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")
