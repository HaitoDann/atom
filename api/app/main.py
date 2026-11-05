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
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import agent, backup, companion, db, hybrid, library, llm, memory, notify, reminders, search, system, telegram
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
    tasks = [asyncio.create_task(reminders.scheduler()), asyncio.create_task(telegram.run()),
             asyncio.create_task(backup.scheduler())]
    yield
    for t in tasks:
        t.cancel()


db.init()
library.init()
app = FastAPI(title="Atom", lifespan=lifespan)
_jobs: set[asyncio.Task] = set()


def background(coro) -> None:
    t = asyncio.create_task(coro)
    _jobs.add(t)
    t.add_done_callback(_jobs.discard)


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
    scope: str = Field(default="auto", pattern="^(auto|none|[0-9,]+)$")
    engine: str = Field(default="default", pattern="^(default|local|mistral|auto)$")


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
            body.scope,
            body.engine,
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
    return {**await system.snapshot(), "last": dict(llm.last_stats)}


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


# ---- mode hybride


class HybridIn(BaseModel):
    mode: str | None = Field(default=None, pattern="^(local|auto|mistral)$")
    allow_memory: bool | None = None
    allow_docs: bool | None = None
    allow_web: bool | None = None
    model: str | None = Field(default=None, max_length=80)


@app.get("/api/hybrid")
def get_hybrid():
    return hybrid.status()


@app.get("/api/hybrid/models")
async def hybrid_models():
    try:
        return {"models": await hybrid.list_models()}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Liste des modèles indisponible : {e}") from e


@app.put("/api/hybrid")
def put_hybrid(body: HybridIn):
    hybrid.save_settings({k: v for k, v in body.model_dump().items() if v is not None})
    return hybrid.status()


# ---- bibliothèque


class CollectionIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = Field(default="docs", pattern="^(docs|code)$")
    source: str | None = Field(default=None, max_length=500)


@app.get("/api/library")
def get_library():
    from .config import PROJECTS_DIR
    return {"collections": library.list_collections(), "server_projects": library.list_server_projects(),
            "projects_dir": str(PROJECTS_DIR)}


@app.post("/api/library/collections")
async def new_collection(body: CollectionIn):
    src = (body.source or "").strip() or None
    if body.kind == "code":
        if not src:
            raise HTTPException(400, "Indique une adresse GitHub ou un dossier du serveur.")
        if not src.startswith(("http://", "https://", "git@")):
            try:
                library.resolve_server_path(src)
            except ValueError as e:
                raise HTTPException(400, str(e)) from e
    cid = library.create_collection(body.name.strip(), body.kind, src)
    if body.kind == "code":
        background(library.index_project(cid))
    return library.get_collection(cid)


@app.patch("/api/library/collections/{cid}")
def patch_collection(cid: int, body: CollectionIn):
    library.rename_collection(cid, body.name.strip())
    return {"ok": True}


@app.delete("/api/library/collections/{cid}")
def remove_collection(cid: int):
    library.delete_collection(cid)
    return {"ok": True}


@app.post("/api/library/collections/{cid}/sync")
async def sync_collection(cid: int):
    col = library.get_collection(cid)
    if not col or col["kind"] != "code":
        raise HTTPException(404, "Projet introuvable")
    background(library.index_project(cid))
    return {"ok": True}


@app.get("/api/library/collections/{cid}/documents")
def collection_documents(cid: int):
    col = library.get_collection(cid)
    if not col:
        raise HTTPException(404, "Collection introuvable")
    return {"collection": col, "documents": library.list_documents(cid),
            "tree": library.tree(cid) if col["kind"] == "code" else None}


@app.post("/api/library/collections/{cid}/documents")
async def upload_document(cid: int, request: Request, name: str):
    col = library.get_collection(cid)
    if not col or col["kind"] != "docs":
        raise HTTPException(404, "Collection introuvable")
    raw = await request.body()
    if not raw:
        raise HTTPException(400, "Fichier vide")
    if len(raw) > 100 * 1024 * 1024:
        raise HTTPException(413, "Fichier trop gros (100 Mo max)")
    did = library.add_document_record(cid, name[:200], raw)
    companion.bump("fed")
    background(library.index_document(did))
    return library.get_document(did)


@app.get("/api/library/documents/{did}")
def document_detail(did: int):
    d = library.get_document(did)
    if not d:
        raise HTTPException(404, "Document introuvable")
    return {"document": d, "chunks": library.document_chunks(did)}


@app.get("/api/library/documents/{did}/file")
def document_file(did: int):
    d = library.get_document(did)
    if not d or not d.get("path") or not str(d["path"]).startswith(str(library.FILES_DIR)):
        raise HTTPException(404, "Fichier introuvable")
    return FileResponse(d["path"], filename=d["name"])


@app.delete("/api/library/documents/{did}")
def remove_document(did: int):
    library.delete_document(did)
    return {"ok": True}


@app.post("/api/library/documents/{did}/reindex")
async def reindex_document(did: int):
    if not library.get_document(did):
        raise HTTPException(404, "Document introuvable")
    background(library.index_document(did))
    return {"ok": True}


@app.get("/api/library/collections/{cid}/file")
def project_file(cid: int, path: str):
    try:
        return {"path": path, "content": library.read_file(cid, path)}
    except FileNotFoundError as e:
        raise HTTPException(404, "Fichier introuvable") from e


# ---- sauvegardes


@app.get("/api/backups")
def get_backups():
    from .config import BACKUP_DIR, BACKUP_KEEP, BACKUP_TIME
    return {"backups": backup.list_all(), "dir": str(BACKUP_DIR), "keep": BACKUP_KEEP, "time": BACKUP_TIME}


@app.post("/api/backups")
def make_backup():
    return backup.create("manual")


@app.get("/api/backups/{name}/download")
def download_backup(name: str):
    try:
        p = backup.path_of(name)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(404, "Sauvegarde introuvable") from e
    return FileResponse(p, filename=name, media_type="application/octet-stream")


@app.post("/api/backups/{name}/restore")
def restore_backup(name: str):
    try:
        return backup.restore_file(backup.path_of(name))
    except FileNotFoundError as e:
        raise HTTPException(404, "Sauvegarde introuvable") from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/export")
def export_db():
    """Télécharge une copie fraîche de toute la mémoire d'Atom."""
    info = backup.create("export")
    return FileResponse(backup.path_of(info["name"]), filename=info["name"].replace("-export", ""),
                        media_type="application/octet-stream")


@app.post("/api/import")
async def import_db(request: Request):
    data = await request.body()
    if len(data) > 500 * 1024 * 1024:
        raise HTTPException(413, "Fichier trop gros")
    if not data.startswith(b"SQLite format 3"):
        raise HTTPException(400, "Ce fichier n'est pas une sauvegarde Atom (.db).")
    tmp = backup._dir() / f"import-{int(time.time())}.tmp"
    tmp.write_bytes(data)
    try:
        return backup.restore_file(tmp)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    finally:
        tmp.unlink(missing_ok=True)


# ---- vitesse


@app.post("/api/benchmark")
async def benchmark(model: str | None = None):
    """Génère un court texte et renvoie la vitesse mesurée par Ollama."""
    m = model or db.kv_get("model") or DEFAULT_MODEL
    t0 = time.time()
    n = 0
    try:
        async for _ in llm.stream_chat(m, [{"role": "user", "content": "Écris une phrase de 40 mots sur la mer. /no_think"}]):
            n += 1
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e)) from e
    return {"model": m, "wall_s": round(time.time() - t0, 2), **llm.last_stats}


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
