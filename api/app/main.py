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
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import health as healthcheck
from . import agent, agentcode, analysis, auth, backup, canvas, proxmox, providers, research, sandbox, spaces, db, ocr, library, llm, observability, reminders, search, telegram, usage
from .config import DEFAULT_MODEL, DEFAULT_PERSONA, EMBED_MODEL, PROVIDER, WEB_DIR

logging.basicConfig(level=logging.INFO)


from .streaming import event


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

    async def maintenance():   # tous les jours : rétention des échanges indexés
        from .config import RECALL_MAX_DAYS, RECALL_MAX_ROWS
        while True:
            try:
                n = await asyncio.to_thread(db.prune_recall, RECALL_MAX_DAYS, RECALL_MAX_ROWS)
                if n:
                    logging.getLogger("atom").info("rétention : %d échanges indexés supprimés", n)
                n = await asyncio.to_thread(usage.prune)
                if n:
                    logging.getLogger("atom").info("rétention : %d appels de modèles supprimés du journal", n)
            except Exception:  # noqa: BLE001
                logging.getLogger("atom").exception("maintenance")
            await asyncio.sleep(86400)
    tasks.append(asyncio.create_task(maintenance()))
    tasks.append(asyncio.create_task(proxmox.scheduler()))
    yield
    for t in tasks:
        t.cancel()


from . import security as _security
_security.install_log_masking()   # aucune clé ni jeton dans les journaux
observability.setup_logging()     # identifiant de requête ; JSON si ATOM_LOG_FORMAT=json

db.init()
library.init()
agentcode.init()
spaces.init()
canvas.init()
auth.init()
providers.restore_health()   # santé des fournisseurs reconstituée depuis le journal des appels
app = FastAPI(title="Atom", lifespan=lifespan)

from .routes import canvas as _r_canvas, git as _r_git  # noqa: E402
app.include_router(_r_canvas.router)
app.include_router(_r_git.router)
import importlib  # noqa: E402

log = logging.getLogger("atom.main")
for _n in ('spaces', 'proxmox_routes', 'feedback', 'mood', 'conversations', 'memories', 'reminders_routes', 'hybrid_routes', 'workshop_routes', 'library_routes', 'code', 'agent_routes', 'sandbox_routes', 'backups', 'lab', 'usage_routes'):
    _m = importlib.import_module(f".routes.{_n}", __package__)
    app.include_router(_m.router)


# ---- protection : tout /api/ demande une session, sauf /api/auth/*
@app.middleware("http")
async def guard(request: Request, call_next):
    path = request.url.path
    metrics_token = path == "/api/metrics" and observability.token_ok(request.headers.get("authorization"))
    if path.startswith("/api/") and not path.startswith("/api/auth/") and not metrics_token:
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
    resp.headers.setdefault("Content-Security-Policy", CSP)
    if _secure(request):
        resp.headers.setdefault("Strict-Transport-Security", "max-age=15552000")
    return resp


# Identifiant de requête, durée et statut (métriques, journaux) : enregistré après « guard », donc exécuté avant lui.
app.middleware("http")(observability.middleware)


@app.get("/api/metrics")
def metrics():
    return PlainTextResponse(observability.render(), media_type="text/plain; version=0.0.4")


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
            log.warning("main : erreur gérée", exc_info=True)
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


# ---- Git (projets clonés par Atom) : chaque action vient d'un bouton


# ---- vitesse


@app.get("/sw.js")
def service_worker():
    # Le service worker doit être servi à la racine et jamais mis en cache.
    return FileResponse(WEB_DIR / "sw.js", media_type="text/javascript",
                        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})


# Politique de sécurité du contenu : seuls les scripts servis par Atom s'exécutent (KaTeX et Mermaid sont
# embarqués dans web/vendor/) ; aucun script en ligne, aucun eval, aucun appel réseau hors d'Atom.
# Les styles en ligne restent permis (attributs style= de l'interface, SVG de Mermaid).
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' data: https://fonts.gstatic.com",
    "img-src 'self' data: blob:",
    "connect-src 'self'",
    "worker-src 'self'",
    "manifest-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


def _asset_version() -> str:
    """Version des fichiers de l'interface (date de modification) : le navigateur recharge dès qu'ils changent."""
    files = [WEB_DIR / "atom.css", WEB_DIR / "index.html", WEB_DIR / "theme.js", *sorted((WEB_DIR / "js").glob("*.js"))]
    m = max(f.stat().st_mtime for f in files if f.exists())
    return format(int(m), "x")


@app.get("/")
def index():
    html = (WEB_DIR / "index.html").read_text("utf-8").replace("__V__", _asset_version())
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})


# Fichiers statiques de l'interface (manifest, icônes…)
app.mount("/", StaticFiles(directory=WEB_DIR), name="web")
