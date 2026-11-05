"""Atom — backend.

- Sert l'interface (web/index.html) sur la même origine.
- Relaie le modèle en streaming (NDJSON) vers le navigateur.
- Conversations multiples, mémoire automatique (faits + rappel sémantique).
- ATOM_PROVIDER=mock permet de tester toute la chaîne sans modèle.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import time
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import agent, companion, db, llm, memory, notify, reminders, search, system, telegram
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


class Attachment(BaseModel):
    name: str = Field(max_length=200)
    text: str = Field(max_length=200_000)


class ChatIn(BaseModel):
    message: str = Field(default="", max_length=8000)
    attachments: list[Attachment] = Field(default_factory=list, max_length=5)
    conversation_id: int | None = None
    model: str | None = None
    persona: str | None = None
    auto_memory: bool = True
    web: str = Field(default="auto", pattern="^(auto|force|off)$")


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
                "embeddings": True, "telegram": telegram.enabled(), "search": search.enabled(),
                "default_model": DEFAULT_MODEL}
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
        "search": search.enabled(),
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
    if not body.message.strip() and not body.attachments:
        raise HTTPException(422, "Message vide")
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
            "",
            [a.model_dump() for a in body.attachments] or None,
            body.web,
        ),
        media_type="application/x-ndjson",
    )


# ---- fichiers joints


class ExtractIn(BaseModel):
    name: str = Field(max_length=200)
    data: str  # base64


TEXT_EXT = {"txt", "md", "markdown", "csv", "tsv", "json", "yaml", "yml", "toml", "ini", "cfg", "conf",
            "log", "xml", "html", "htm", "css", "js", "ts", "tsx", "jsx", "py", "sh", "bash", "sql",
            "c", "h", "cpp", "hpp", "rs", "go", "java", "kt", "rb", "php", "lua", "env", "dockerfile"}


@app.post("/api/extract")
def extract(body: ExtractIn):
    """Renvoie le texte d'un fichier (texte brut, code, PDF)."""
    try:
        raw = base64.b64decode(body.data, validate=False)
    except ValueError as e:
        raise HTTPException(400, "Fichier illisible") from e
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(413, "Fichier trop gros (15 Mo max)")
    ext = body.name.rsplit(".", 1)[-1].lower() if "." in body.name else body.name.lower()
    if ext == "pdf" or raw[:5] == b"%PDF-":
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(raw))
            pages = [p.extract_text() or "" for p in reader.pages[:200]]
            text = "\n\n".join(f"--- page {i + 1} ---\n{t.strip()}" for i, t in enumerate(pages) if t.strip())
        except Exception as e:  # noqa: BLE001
            raise HTTPException(400, f"PDF illisible : {e}") from e
        if not text.strip():
            raise HTTPException(400, "Ce PDF ne contient pas de texte (document scanné ?).")
        return {"name": body.name, "text": text[:200_000], "pages": len(reader.pages)}
    if ext in {"png", "jpg", "jpeg", "gif", "webp", "heic", "bmp"}:
        raise HTTPException(415, "Les images ne sont pas encore lues : le modèle actuel ne voit pas.")
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if "\x00" in text[:2000]:
        raise HTTPException(415, "Format non pris en charge (fichier binaire).")
    return {"name": body.name, "text": text[:200_000]}


# ---- avis sur les réponses


class FeedbackIn(BaseModel):
    value: int | None = Field(default=None, ge=-1, le=1)  # 1 = 👍, -1 = 👎, None = retirer
    reason: str | None = Field(default=None, max_length=500)


@app.patch("/api/messages/{mid}")
def feedback(mid: int, body: FeedbackIn):
    if not db.set_feedback(mid, body.value, body.reason):
        raise HTTPException(404, "Message introuvable")
    return {"ok": True}


# ---- le lien (côté compagnon)


@app.get("/api/companion")
def get_companion():
    return companion.state()


@app.post("/api/companion/pet")
def pet():
    companion.bump("pets")
    return companion.state()


# ---- humeur


@app.get("/api/mood")
def mood(hours: int = 24):
    return {"events": db.emotions_since(time.time() - hours * 3600), "now": time.time()}


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
def search_conversations(q: str):
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


@app.get("/sw.js")
def service_worker():
    # Le service worker doit être servi à la racine et jamais mis en cache.
    return FileResponse(WEB_DIR / "sw.js", media_type="text/javascript",
                        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-cache"})


# Fichiers statiques de l'interface (manifest, icônes…)
app.mount("/", StaticFiles(directory=WEB_DIR), name="web")
