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
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import health as healthcheck
from . import agent, agentcode, analysis, auth, backup, canvas, codeedit, research, sandbox, spaces, db, gitops, models_lab, ocr, providers, hybrid, library, llm, memory, notify, reminders, search, system, telegram, workshop
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
    asyncio.create_task(sandbox.cleanup())
    yield
    for t in tasks:
        t.cancel()


db.init()
library.init()
agentcode.init()
spaces.init()
canvas.init()
auth.init()
app = FastAPI(title="Atom", lifespan=lifespan)


# ---- protection : tout /api/ demande une session, sauf /api/auth/*
@app.middleware("http")
async def guard(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and not path.startswith("/api/auth/"):
        if not auth.is_set() or not auth.session_for(request.cookies.get(auth.COOKIE)):
            return JSONResponse({"detail": "Connexion requise", "auth": True}, status_code=401)
        # Protection CSRF : les requêtes qui modifient quelque chose doivent venir de l'interface.
        if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get("x-atom") != "1":
            return JSONResponse({"detail": "Requête refusée"}, status_code=403)
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if _secure(request):
        resp.headers.setdefault("Strict-Transport-Security", "max-age=15552000")
    return resp


def _ip(request: Request) -> str:
    return request.client.host if request.client else "?"


def _secure(request: Request) -> bool:
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"


class PasswordIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)


class PasswordChangeIn(BaseModel):
    current: str = Field(min_length=1, max_length=200)
    new: str = Field(min_length=1, max_length=200)


def _login_response(request: Request, payload: dict) -> JSONResponse:
    token = auth.create_session(auth.device_name(request.headers.get("user-agent", "")), _ip(request))
    resp = JSONResponse(payload)
    resp.set_cookie(auth.COOKIE, token, max_age=auth.SESSION_DAYS * 86400, httponly=True,
                    samesite="lax", secure=_secure(request), path="/")
    return resp


@app.get("/api/auth/status")
def auth_status(request: Request):
    s = auth.session_for(request.cookies.get(auth.COOKIE))
    return {"setup_needed": not auth.is_set(), "authenticated": bool(s and auth.is_set()),
            "session_id": s["id"] if s else None}


@app.post("/api/auth/setup")
def auth_setup(body: PasswordIn, request: Request):
    if auth.is_set():
        raise HTTPException(409, "Un mot de passe existe déjà.")
    try:
        auth.set_password(body.password)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return _login_response(request, {"ok": True})


@app.post("/api/auth/login")
def auth_login(body: PasswordIn, request: Request):
    ip = _ip(request)
    wait = auth.blocked_for(ip)
    if wait:
        raise HTTPException(429, f"Trop d'essais. Réessaie dans {wait // 60 + 1} min.")
    if not auth.is_set() or not auth.check_password(body.password):
        auth.record_failure(ip)
        raise HTTPException(401, "Mot de passe incorrect.")
    auth.record_success(ip)
    return _login_response(request, {"ok": True})


@app.post("/api/auth/logout")
def auth_logout(request: Request):
    auth.revoke(token=request.cookies.get(auth.COOKIE))
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(auth.COOKIE, path="/")
    return resp


@app.get("/api/security/sessions")
def security_sessions(request: Request):
    cur = auth.session_for(request.cookies.get(auth.COOKIE))
    return {"sessions": auth.list_sessions(), "current": cur["id"] if cur else None}


@app.delete("/api/security/sessions/{sid}")
def security_revoke(sid: int):
    auth.revoke(sid=sid)
    return {"ok": True}


@app.post("/api/security/password")
def security_password(body: PasswordChangeIn, request: Request):
    if not auth.check_password(body.current):
        raise HTTPException(401, "Mot de passe actuel incorrect.")
    try:
        auth.set_password(body.new)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    cur = auth.session_for(request.cookies.get(auth.COOKIE))
    auth.revoke(all_but=cur["id"] if cur else -1)   # les autres appareils devront se reconnecter
    return {"ok": True}


@app.get("/api/status")
async def status_report():
    return await healthcheck.report()
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
    space_id: int | None = None


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
            body.space_id,
        ),
        media_type="application/x-ndjson",
    )


# ---- espaces


class SpaceIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    instructions: str | None = Field(default=None, max_length=8000)
    collections: list[int] | None = Field(default=None, max_length=50)


@app.get("/api/spaces")
def get_spaces():
    return {"spaces": spaces.list_all()}


@app.post("/api/spaces")
def post_space(body: SpaceIn):
    if not body.name:
        raise HTTPException(422, "Nom manquant")
    sid = spaces.create(body.name, body.instructions or "", body.collections or [])
    return spaces.get(sid)


@app.patch("/api/spaces/{sid}")
def patch_space(sid: int, body: SpaceIn):
    if not spaces.get(sid):
        raise HTTPException(404, "Espace introuvable")
    spaces.update(sid, **{k: v for k, v in body.model_dump().items() if v is not None})
    return spaces.get(sid)


@app.delete("/api/spaces/{sid}")
def del_space(sid: int):
    spaces.delete(sid)
    return {"ok": True}


class ConvSpaceIn(BaseModel):
    space_id: int | None = None


@app.put("/api/conversations/{cid}/space")
def put_conv_space(cid: int, body: ConvSpaceIn):
    if body.space_id and not spaces.get(body.space_id):
        raise HTTPException(404, "Espace introuvable")
    spaces.assign(cid, body.space_id)
    return {"ok": True}


# ---- recherche approfondie, analyse de données, canevas


class ResearchIn(BaseModel):
    message: str = Field(min_length=3, max_length=4000)
    conversation_id: int | None = None


@app.post("/api/research")
async def research_run(body: ResearchIn):
    return StreamingResponse((event(**ev) async for ev in research.run(body.message.strip(), body.conversation_id)),
                             media_type="application/x-ndjson")


class AnalyzeIn(BaseModel):
    name: str = Field(max_length=200)
    data: str = Field(max_length=70_000_000)   # base64 (50 Mo)
    question: str = Field(default="", max_length=4000)
    conversation_id: int | None = None


@app.post("/api/analyze")
async def analyze_run(body: AnalyzeIn):
    raw = analysis.decode(body.data)
    if len(raw) > 50 * 1024 * 1024:
        raise HTTPException(413, "Fichier trop gros (50 Mo max)")
    return StreamingResponse((event(**ev) async for ev in analysis.run(body.name, raw, body.question, body.conversation_id)),
                             media_type="application/x-ndjson")


@app.get("/api/analysis/{fid}")
def analysis_image(fid: str):
    p = analysis.image_path(fid)
    if not p:
        raise HTTPException(404, "Image introuvable")
    return FileResponse(p)


@app.get("/api/sandbox")
def sandbox_global():
    return sandbox.status()


class CanvasIn(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    content: str | None = Field(default=None, max_length=400_000)
    conversation_id: int | None = None
    kind: str | None = Field(default=None, pattern="^(doc|code)$")


class CanvasEditIn(BaseModel):
    instruction: str = Field(min_length=2, max_length=2000)
    selection: str = Field(default="", max_length=100_000)
    engine: str = Field(default="auto", pattern="^(auto|local)$")


@app.get("/api/canvas")
def canvas_list(conversation_id: int | None = None):
    return {"canvases": canvas.list_for(conversation_id)}


@app.post("/api/canvas")
def canvas_create(body: CanvasIn):
    cid = canvas.create(body.title or "Sans titre", body.content or "", body.conversation_id, body.kind or "doc")
    return canvas.get(cid)


@app.get("/api/canvas/{cid}")
def canvas_get(cid: int):
    c = canvas.get(cid)
    if not c:
        raise HTTPException(404, "Canevas introuvable")
    return c


@app.put("/api/canvas/{cid}")
def canvas_put(cid: int, body: CanvasIn):
    try:
        cur = canvas.get(cid) or {}
        return canvas.save(cid, body.content if body.content is not None else cur.get("content", ""), "toi", "", body.title)
    except KeyError as e:
        raise HTTPException(404, "Canevas introuvable") from e


@app.post("/api/canvas/{cid}/edit")
async def canvas_edit(cid: int, body: CanvasEditIn):
    try:
        return await canvas.edit(cid, body.instruction, body.selection, body.engine)
    except KeyError as e:
        raise HTTPException(404, "Canevas introuvable") from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Modification impossible : {e}") from e


@app.get("/api/canvas/{cid}/versions/{i}")
def canvas_version(cid: int, i: int):
    try:
        return {"content": canvas.version(cid, i)}
    except KeyError as e:
        raise HTTPException(404, "Version introuvable") from e


@app.delete("/api/canvas/{cid}")
def canvas_delete(cid: int):
    canvas.delete(cid)
    return {"ok": True}


# ---- fichiers joints


class ExtractIn(BaseModel):
    name: str = Field(max_length=200)
    data: str = Field(max_length=21_000_000)  # base64 (15 Mo)


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
            scanned = {i + 1 for i, t in enumerate(pages) if len(t.strip()) < 40}
            ocr_used = False
            if scanned and ocr.pdf_available():
                got = dict(ocr.pdf_pages(raw, max_pages=30, only=scanned))
                pages = [got.get(i + 1, t) for i, t in enumerate(pages)]
                ocr_used = bool(got)
            text = "\n\n".join(f"--- page {i + 1} ---\n{t.strip()}" for i, t in enumerate(pages) if t.strip())
        except Exception as e:  # noqa: BLE001
            raise HTTPException(400, f"PDF illisible : {e}") from e
        if not text.strip():
            raise HTTPException(400, "Ce PDF ne contient pas de texte lisible." if ocr.pdf_available()
                                else "Ce PDF ne contient pas de texte (document scanné ?) et l'OCR n'est pas installé.")
        return {"name": body.name, "text": text[:200_000], "pages": len(reader.pages), "ocr": ocr_used}
    if ext in ocr.IMAGE_EXT:
        if not ocr.available():
            raise HTTPException(415, "Lecture des images (OCR) indisponible sur ce serveur.")
        text = ocr.image_text(raw, ext)
        if not text:
            raise HTTPException(415, "Aucun texte trouvé dans l'image (Atom lit le texte, il ne voit pas les images).")
        return {"name": body.name, "text": text[:200_000], "ocr": True}
    if ext == "heic":
        raise HTTPException(415, "Format HEIC non pris en charge : exporte l'image en JPEG.")
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
    provider: str | None = Field(default=None, max_length=40)


class ProviderModelIn(BaseModel):
    model: str = Field(max_length=120)


@app.put("/api/hybrid/providers/{pid}")
def put_provider(pid: str, body: ProviderModelIn):
    if not providers.get(pid):
        raise HTTPException(404, "Fournisseur inconnu")
    providers.set_model(pid, body.model)
    return hybrid.status()


@app.get("/api/hybrid")
def get_hybrid():
    return hybrid.status()


@app.get("/api/hybrid/models")
async def hybrid_models(provider: str | None = None):
    try:
        return {"models": await hybrid.list_models(provider)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Liste des modèles indisponible : {e}") from e


@app.put("/api/hybrid")
def put_hybrid(body: HybridIn):
    hybrid.save_settings({k: v for k, v in body.model_dump().items() if v is not None})
    return hybrid.status()


# ---- atelier multi-IA


class WorkshopIn(BaseModel):
    enabled: bool | None = None
    pattern: str | None = Field(default=None, pattern="^(review|panel|debate)$")
    participants: list[str] | None = Field(default=None, max_length=3)
    rounds: int | None = Field(default=None, ge=1, le=3)


class WorkshopRunIn(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: int | None = None
    pattern: str | None = Field(default=None, pattern="^(review|panel|debate)$")
    participants: list[str] | None = Field(default=None, max_length=3)


@app.get("/api/workshop")
def get_workshop():
    s = workshop.settings()
    opts = [{"id": "auto", "label": "Automatique"}, {"id": "local", "label": workshop.engine_label("local")}]
    opts += [{"id": f"p:{p.id}", "label": workshop.engine_label(f"p:{p.id}"), "family": providers.family_of(providers.model_of(p), p.family),
              "strength": p.strength} for p in providers.ALL if p.configured]
    assigned = workshop.assign(s["pattern"], s["participants"])
    return {**s, "patterns": workshop.PATTERNS, "roles": workshop.ROLES, "options": opts,
            "assigned": [workshop.engine_label(x) for x in assigned], "warnings": workshop.warnings(s["pattern"], s["participants"])}


@app.put("/api/workshop")
def put_workshop(body: WorkshopIn):
    workshop.save_settings({k: v for k, v in body.model_dump().items() if v is not None})
    return get_workshop()


@app.post("/api/workshop/run")
async def run_workshop(body: WorkshopRunIn):
    if not workshop.settings()["enabled"]:
        raise HTTPException(400, "L'atelier est désactivé (Réglages → Atelier).")
    return StreamingResponse(
        (event(**ev) async for ev in workshop.run(body.message.strip(), body.conversation_id, body.pattern, body.participants)),
        media_type="application/x-ndjson")


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


@app.get("/api/library/collections/{cid}/grep")
def project_grep(cid: int, q: str):
    """Recherche texte dans un projet de code : [{path, line, text}]."""
    q = q.strip()
    if len(q) < 2:
        return {"matches": []}
    try:
        return {"matches": library.grep(cid, q)}
    except FileNotFoundError as e:
        raise HTTPException(404, "Projet introuvable") from e


@app.get("/api/library/collections/{cid}/file")
def project_file(cid: int, path: str):
    try:
        return {"path": path, "content": library.read_file(cid, path)}
    except FileNotFoundError as e:
        raise HTTPException(404, "Fichier introuvable") from e


# ---- mode Code : modifications proposées


class ProposeIn(BaseModel):
    path: str = Field(max_length=500)
    instruction: str = Field(min_length=2, max_length=4000)
    start: int | None = None
    end: int | None = None
    engine: str = "local"


@app.post("/api/code/{cid}/propose")
async def code_propose(cid: int, body: ProposeIn):
    try:
        return await codeedit.propose(cid, body.path, body.instruction, body.start, body.end, body.engine)
    except FileNotFoundError as e:
        raise HTTPException(404, "Fichier introuvable") from e
    except UnicodeDecodeError as e:
        raise HTTPException(415, "Fichier non texte") from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Le modèle n'a pas répondu : {e}") from e


@app.post("/api/code/proposals/{pid}/apply")
def code_apply(pid: str):
    try:
        out = codeedit.apply(pid)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e
    return out


@app.get("/api/code/{cid}/changes")
def code_changes(cid: int):
    try:
        return codeedit.changes(cid)
    except FileNotFoundError as e:
        raise HTTPException(404, "Projet introuvable") from e


class RevertIn(BaseModel):
    path: str = Field(max_length=500)


@app.post("/api/code/{cid}/revert")
def code_revert(cid: int, body: RevertIn):
    try:
        codeedit.revert(cid, body.path)
    except FileNotFoundError as e:
        raise HTTPException(404, "Fichier introuvable") from e
    except (PermissionError, RuntimeError) as e:
        raise HTTPException(409, str(e)) from e
    return {"ok": True}


# ---- mode agent (Code)


class AgentIn(BaseModel):
    task: str = Field(min_length=3, max_length=4000)
    engine: str = Field(default="remote", pattern="^(remote|local)$")
    parent: str | None = Field(default=None, max_length=32)


@app.post("/api/agent/{cid}")
async def agent_start(cid: int, body: AgentIn):
    """Lance l'agent en arrière-plan : il continue même si la page est rechargée ou fermée."""
    if not library.get_collection(cid):
        raise HTTPException(404, "Projet introuvable")
    return {"id": agentcode.start(cid, body.task, body.engine, body.parent)}


class RulesIn(BaseModel):
    rules: list[str] = Field(default_factory=list, max_length=40)


@app.get("/api/agent/{cid}/rules")
def agent_rules(cid: int):
    return {"rules": agentcode.get_rules(cid)}


@app.put("/api/agent/{cid}/rules")
def agent_rules_put(cid: int, body: RulesIn):
    return {"rules": agentcode.set_rules(cid, body.rules)}


@app.get("/api/agent/{cid}/runs")
def agent_runs(cid: int):
    return {"runs": agentcode.list_runs(cid)}


@app.get("/api/agent/runs/{rid}")
def agent_get(rid: str, after: int = 0):
    r = agentcode.get_run(rid)
    if not r:
        raise HTTPException(404, "Tâche introuvable")
    return {"id": rid, "collection_id": r["collection_id"], "task": r["task"], "status": r["status"], "parent": r["parent"],
            "created_at": r["created_at"], "events": r["events"][after:], "total": len(r["events"])}


@app.post("/api/agent/runs/{rid}/stop")
def agent_stop(rid: str):
    agentcode.stop(rid)
    return {"ok": True}


@app.delete("/api/agent/runs/{rid}")
def agent_delete(rid: str):
    agentcode.stop(rid)
    agentcode.delete_run(rid)
    return {"ok": True}


class AgentApplyIn(BaseModel):
    paths: list[str] = Field(default_factory=list, max_length=500)


@app.post("/api/agent/runs/{rid}/apply")
async def agent_apply(rid: str, body: AgentApplyIn):
    try:
        out = agentcode.apply(rid, body.paths)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e
    if out["applied"]:
        background(library.index_project(out["collection_id"]))
    return out


# ---- bac à sable (tests dans un conteneur jetable)


class SandboxCmd(BaseModel):
    command: str = Field(default="", max_length=500)


class SandboxRun(BaseModel):
    command: str | None = Field(default=None, max_length=500)
    run_id: str | None = Field(default=None, max_length=32)   # tester les modifications d'une tâche de l'agent


@app.get("/api/sandbox/{cid}")
def sandbox_info(cid: int):
    with db.conn() as c:
        files = [r["path"] for r in c.execute("SELECT path FROM documents WHERE collection_id = ?", (cid,))]
    col = library.get_collection(cid)
    if col and col["kind"] == "code":   # les fichiers de projet (go.mod, Cargo.toml…) ne sont pas tous indexés
        root = library._code_root(col)
        if root.is_dir():
            files += [p.name for p in root.iterdir() if p.is_file()]
    return {**sandbox.status(), "command": sandbox.default_command(cid, files), "lang": sandbox.detect(files)}


@app.put("/api/sandbox/{cid}")
def sandbox_set(cid: int, body: SandboxCmd):
    sandbox.set_command(cid, body.command)
    return sandbox_info(cid)


@app.post("/api/sandbox/{cid}/run")
async def sandbox_run(cid: int, body: SandboxRun):
    overlay = None
    if body.run_id:
        r = agentcode.get_run(body.run_id)
        overlay = {k: v[1] for k, v in (r or {}).get("files", {}).items()} if r else None
    return StreamingResponse((event(**ev) async for ev in sandbox.run(cid, body.command, overlay)),
                             media_type="application/x-ndjson")


# ---- Git (projets clonés par Atom) : chaque action vient d'un bouton


def _git_call(fn, *a):
    try:
        return fn(*a)
    except FileNotFoundError as e:
        raise HTTPException(404, "Projet introuvable") from e
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e
    except (ValueError, gitops.GitError) as e:
        raise HTTPException(409, str(e)) from e


class GitName(BaseModel):
    name: str = Field(max_length=100)


class GitCommit(BaseModel):
    message: str = Field(max_length=5000)
    paths: list[str] = Field(max_length=500)


class GitPaths(BaseModel):
    paths: list[str] = Field(default_factory=list, max_length=500)


@app.get("/api/git/{cid}/status")
def git_status(cid: int):
    return _git_call(gitops.status, cid)


@app.get("/api/git/{cid}/diff")
def git_diff(cid: int):
    return {"diff": _git_call(gitops.diff, cid, None)}


@app.post("/api/git/{cid}/branch")
def git_branch(cid: int, body: GitName):
    return _git_call(gitops.new_branch, cid, body.name)


@app.post("/api/git/{cid}/switch")
async def git_switch(cid: int, body: GitName):
    out = _git_call(gitops.switch, cid, body.name)
    background(library.index_project(cid))   # les fichiers ont changé : réindexation (seuls les fichiers modifiés)
    return out


@app.post("/api/git/{cid}/commit")
def git_commit(cid: int, body: GitCommit):
    return _git_call(gitops.commit, cid, body.message, body.paths)


@app.post("/api/git/{cid}/push")
def git_push(cid: int):
    return _git_call(gitops.push, cid)


@app.post("/api/git/{cid}/discard")
async def git_discard(cid: int):
    out = _git_call(gitops.discard_all, cid)
    background(library.index_project(cid))
    return out


@app.post("/api/git/{cid}/message")
async def git_message(cid: int, body: GitPaths):
    try:
        return {"message": await gitops.suggest_message(cid, body.paths)}
    except (FileNotFoundError, PermissionError, ValueError, gitops.GitError) as e:
        raise HTTPException(409, str(e)) from e


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


# ---- labo des modèles locaux


class ModelName(BaseModel):
    name: str = Field(min_length=2, max_length=120, pattern=r"^[A-Za-z0-9._:/-]+$")


class CompareIn(BaseModel):
    models: list[str] = Field(min_length=1, max_length=4)
    prompts: list[str] = Field(default_factory=list, max_length=4)   # ids de PROMPTS
    custom: str = Field(default="", max_length=2000)


@app.get("/api/lab")
async def lab():
    try:
        installed = [] if PROVIDER == "mock" else await llm.installed_models()
    except httpx.HTTPError:
        installed = []
    if PROVIDER == "mock":
        installed = ["mock", "qwen3:4b-instruct-2507-q4_K_M"]
    from . import system
    snap = await system.snapshot()
    return {"installed": [n for n in installed if n.split(":")[0] != EMBED_MODEL.split(":")[0]],
            "suggested": models_lab.SUGGESTED, "prompts": [{"id": p["id"], "label": p["label"]} for p in models_lab.PROMPTS],
            "pulls": models_lab.pulls(), "memory": snap.get("memory"), "current": db.kv_get("model") or DEFAULT_MODEL,
            "remote": [{"id": f"p:{p.id}", "name": p.name, "model": providers.model_of(p), "left": providers.quota_left(p.id)}
                       for p in providers.ALL if p.configured]}


@app.post("/api/lab/install")
async def lab_install(body: ModelName):
    st = next((p for p in models_lab.pulls() if p["name"] == body.name), None)
    if st and not st["done"]:
        raise HTTPException(409, "Installation déjà en cours")
    background(models_lab.install(body.name))
    return {"ok": True}


@app.post("/api/lab/delete")
async def lab_delete(body: ModelName):
    if body.name == (db.kv_get("model") or DEFAULT_MODEL):
        raise HTTPException(409, "C'est le modèle utilisé par Atom : choisis-en un autre avant de le supprimer.")
    try:
        await models_lab.delete(body.name)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e)) from e
    return {"ok": True}


@app.post("/api/lab/compare")
async def lab_compare(body: CompareIn):
    prompts = [p for p in models_lab.PROMPTS if p["id"] in body.prompts]
    if body.custom.strip():
        prompts.append({"id": "perso", "label": "Ta question", "text": body.custom.strip()})
    if not prompts:
        raise HTTPException(422, "Choisis au moins une question")
    keep = db.kv_get("model") or DEFAULT_MODEL
    return StreamingResponse((event(**ev) async for ev in models_lab.compare(body.models, prompts, keep)),
                             media_type="application/x-ndjson")


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
