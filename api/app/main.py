"""Atom — backend minimal.

- Sert l'interface (web/index.html) sur la même origine : pas de CORS à gérer.
- Relaie Ollama en streaming (NDJSON) vers le navigateur.
- Stocke l'historique et les souvenirs dans SQLite, côté serveur.
- ATOM_PROVIDER=mock permet de tester toute la chaîne sans modèle.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import re
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
DEFAULT_MODEL = os.getenv("ATOM_MODEL", "qwen3:4b-instruct-2507-q4_K_M")
PROVIDER = os.getenv("ATOM_PROVIDER", "ollama")  # "ollama" | "mock"
DB_PATH = Path(os.getenv("ATOM_DB", "data/atom.db"))
WEB_DIR = Path(os.getenv("ATOM_WEB", Path(__file__).resolve().parents[2] / "web"))
CONTEXT_TURNS = int(os.getenv("ATOM_CONTEXT_TURNS", "20"))

EMOTIONS = ["idle", "thinking", "talking", "joy", "angry", "sad", "surprise", "fear", "sleep"]

DEFAULT_PERSONA = (
    "Tu es Atom, une entité numérique bienveillante, curieuse et concise. "
    "Tu parles français avec naturel et chaleur."
)

# --------------------------------------------------------------------------
# Stockage
# --------------------------------------------------------------------------


def db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(db()) as c, c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                emotion TEXT,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            """
        )


def add_message(role: str, content: str, emotion: str | None = None) -> None:
    with closing(db()) as c, c:
        c.execute(
            "INSERT INTO messages (role, content, emotion, created_at) VALUES (?, ?, ?, ?)",
            (role, content, emotion, time.time()),
        )


def recent_messages(limit: int) -> list[dict]:
    with closing(db()) as c:
        rows = c.execute(
            "SELECT role, content, emotion FROM messages ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def list_memories() -> list[str]:
    with closing(db()) as c:
        return [r["content"] for r in c.execute("SELECT content FROM memories ORDER BY id")]


# --------------------------------------------------------------------------
# Agent
# --------------------------------------------------------------------------

TAG_RE = re.compile(r"^\s*\[([a-zA-Z]+)\]\s*")


def system_prompt(persona: str) -> str:
    s = (
        f"{persona.strip()}\n\n"
        "Tu possèdes un corps : une sphère de fragments lumineux qui exprime ton état.\n"
        "Réponds en une à trois phrases courtes, simplement.\n"
        "Commence TOUJOURS ta réponse par ton émotion entre crochets, puis ton message. "
        f"Émotions possibles : {', '.join(EMOTIONS)}.\n"
        "Ne réfléchis pas à voix haute, ne décris pas ton raisonnement : réponds directement.\n"
        "Exemple : [joy] Ravi de te revoir !\n"
        "(talking = neutre, joy = content, sad = triste, angry = agacé, surprise = étonné, "
        "fear = inquiet, thinking = perplexe, sleep = fatigué, idle = calme)"
    )
    mems = list_memories()
    s += "\n/no_think"
    if mems:
        s += "\n\nCe que tu sais durablement de l'utilisateur :\n" + "\n".join(f"- {m}" for m in mems)
    return s


def event(**kw) -> bytes:
    return (json.dumps(kw, ensure_ascii=False) + "\n").encode()


async def ollama_tokens(model: str, messages: list[dict]) -> AsyncIterator[str]:
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "think": False,
        # num_predict borne la longueur : un petit modèle qui part en boucle s'arrête vite.
        "options": {"temperature": 0.7, "num_predict": 300, "repeat_penalty": 1.15},
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(10, read=300)) as client:
        async with client.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload) as r:
            if r.status_code != 200:
                body = (await r.aread()).decode(errors="replace")[:300]
                if r.status_code == 404 and "not found" in body:
                    raise RuntimeError(
                        f"Le modèle « {model} » n'est pas encore installé (téléchargement en cours ?). "
                        f"Vérifie avec : docker compose logs ollama-pull"
                    )
                raise RuntimeError(f"Ollama a répondu {r.status_code} : {body}")
            async for line in r.aiter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                if chunk.get("error"):
                    raise RuntimeError(chunk["error"])
                text = chunk.get("message", {}).get("content", "")
                if text:
                    yield text
                if chunk.get("done"):
                    break


async def mock_tokens(model: str, messages: list[dict]) -> AsyncIterator[str]:
    user = messages[-1]["content"]
    emotion = random.choice(["talking", "joy", "surprise"])
    reply = f"[{emotion}] (mode test) Tu m'as dit : « {user} ». Tout fonctionne de bout en bout."
    for word in re.findall(r"\S+\s*", reply):
        await asyncio.sleep(0.06)
        yield word


async def run_chat(message: str, model: str, persona: str) -> AsyncIterator[bytes]:
    history = recent_messages(CONTEXT_TURNS * 2)
    msgs = [{"role": "system", "content": system_prompt(persona)}]
    msgs += [{"role": m["role"], "content": m["content"]} for m in history]
    msgs.append({"role": "user", "content": message})
    add_message("user", message)

    source = mock_tokens if PROVIDER == "mock" else ollama_tokens
    emotion: str | None = None
    head = ""  # tampon tant que le tag d'émotion n'est pas résolu
    text = ""
    try:
        async for tok in source(model, msgs):
            if emotion is None:
                head += tok
                # Raisonnement interne (modèles "thinking") : on l'écarte entièrement.
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
        add_message("assistant", text, emotion)
        yield event(type="done", emotion=emotion)
    except Exception as e:  # noqa: BLE001 — on renvoie l'erreur à l'interface
        msg = str(e) or e.__class__.__name__
        if isinstance(e, httpx.ConnectError):
            msg = f"Impossible de joindre Ollama sur {OLLAMA_URL}."
        yield event(type="error", message=msg)


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------

app = FastAPI(title="Atom")
init_db()


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    model: str | None = None
    persona: str | None = None


class MemoriesIn(BaseModel):
    memories: list[str]


@app.get("/api/health")
async def health():
    ollama_ok = model_ready = PROVIDER == "mock"
    if not ollama_ok:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                r = await client.get(f"{OLLAMA_URL}/api/tags")
                ollama_ok = r.status_code == 200
                model_ready = ollama_ok and bool(r.json().get("models"))
        except (httpx.HTTPError, ValueError):
            pass
    return {"ok": True, "provider": PROVIDER, "ollama": ollama_ok, "model_ready": model_ready,
            "default_model": DEFAULT_MODEL}


@app.get("/api/models")
async def models():
    if PROVIDER == "mock":
        return {"models": ["mock"], "default": "mock"}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            r.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Ollama injoignable : {e}") from e
    return {"models": [m["name"] for m in r.json().get("models", [])], "default": DEFAULT_MODEL}


@app.post("/api/chat")
async def chat(body: ChatIn):
    model = body.model or DEFAULT_MODEL
    persona = body.persona or DEFAULT_PERSONA
    return StreamingResponse(
        run_chat(body.message.strip(), model, persona), media_type="application/x-ndjson"
    )


@app.get("/api/history")
def get_history():
    return {"messages": recent_messages(500)}


@app.delete("/api/history")
def clear_history():
    with closing(db()) as c, c:
        c.execute("DELETE FROM messages")
    return {"ok": True}


@app.get("/api/memories")
def get_memories():
    return {"memories": list_memories()}


@app.put("/api/memories")
def put_memories(body: MemoriesIn):
    items = [m.strip() for m in body.memories if m.strip()]
    with closing(db()) as c, c:
        c.execute("DELETE FROM memories")
        c.executemany(
            "INSERT INTO memories (content, created_at) VALUES (?, ?)",
            [(m, time.time()) for m in items],
        )
    return {"memories": items}


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")
