"""État d'Atom : vérifie chaque service et signale ce qui ne va pas."""

from __future__ import annotations

import asyncio
import os
import shutil
import time

import httpx

from . import backup, db, hybrid, library, ocr, search, telegram
from .config import (DATA_DIR, DB_PATH, DEFAULT_MODEL, EMBED_MODEL, NTFY_URL, OLLAMA_URL, PROVIDER, SEARXNG_URL,
                     TELEGRAM_ALLOWED, TELEGRAM_TOKEN)

VERSION = os.getenv("ATOM_VERSION", "dev")


def _c(name: str, status: str, detail: str, hint: str = "") -> dict:
    return {"name": name, "status": status, "detail": detail, "hint": hint}   # status : ok | warn | error | off


async def _ollama() -> list[dict]:
    if PROVIDER == "mock":
        return [_c("Modèle local", "ok", "mode test (sans modèle)")]
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            tags = (await client.get(f"{OLLAMA_URL}/api/tags")).json().get("models", [])
            loaded = (await client.get(f"{OLLAMA_URL}/api/ps")).json().get("models", [])
    except (httpx.HTTPError, ValueError) as e:
        return [_c("Ollama", "error", f"injoignable ({e.__class__.__name__})", "docker compose logs ollama")]
    names = [m["name"] for m in tags]
    chat = db.kv_get("model") or DEFAULT_MODEL
    out = [_c("Ollama", "ok", f"{len(names)} modèle(s) installé(s), {len(loaded)} chargé(s) en mémoire")]
    out.append(_c("Modèle de discussion", "ok" if chat in names else "error", chat,
                  "" if chat in names else f"docker compose exec ollama ollama pull {chat}"))
    has_embed = any(n.split(":")[0] == EMBED_MODEL.split(":")[0] for n in names)
    out.append(_c("Modèle de mémoire", "ok" if has_embed else "warn", EMBED_MODEL if has_embed else "absent : mémoire et bibliothèque dégradées",
                  "" if has_embed else f"docker compose exec ollama ollama pull {EMBED_MODEL}"))
    return out


async def _http(name: str, url: str, path: str, hint: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            r = await client.get(url + path)
        return _c(name, "ok" if r.status_code < 500 else "error", f"répond ({r.status_code})")
    except httpx.HTTPError as e:
        return _c(name, "error", f"injoignable ({e.__class__.__name__})", hint)


async def _telegram() -> dict:
    if not TELEGRAM_TOKEN:
        return _c("Telegram", "off", "désactivé", "ATOM_TELEGRAM_TOKEN dans .env")
    if not TELEGRAM_ALLOWED:
        return _c("Telegram", "warn", "aucun identifiant autorisé", "ATOM_TELEGRAM_ALLOWED dans .env")
    try:
        async with httpx.AsyncClient(timeout=6) as client:
            me = await telegram.call(client, "getMe")
        return _c("Telegram", "ok", f"@{me.get('username')} · {len(TELEGRAM_ALLOWED)} utilisateur(s) autorisé(s)")
    except Exception as e:  # noqa: BLE001
        return _c("Telegram", "error", str(e)[:120], "vérifie le jeton dans .env")


async def _remote() -> dict:
    if not hybrid.configured():
        return _c(f"Mode hybride ({hybrid.REMOTE_NAME})", "off", "non configuré", "ATOM_REMOTE_API_KEY dans .env")
    try:
        models = await hybrid.list_models()
        ok = hybrid.model() in models or not models
        return _c(f"Mode hybride ({hybrid.REMOTE_NAME})", "ok" if ok else "warn",
                  f"{hybrid.model()} · {hybrid.used_today()}/{hybrid.REMOTE_DAILY_LIMIT} aujourd'hui"
                  + ("" if ok else " · modèle introuvable"), "" if ok else "Réglages → Hybride → choisir un modèle")
    except Exception as e:  # noqa: BLE001
        return _c(f"Mode hybride ({hybrid.REMOTE_NAME})", "error", str(e)[:120], "vérifie la clé et l'adresse dans .env")


def _storage() -> list[dict]:
    out = []
    try:
        du = shutil.disk_usage(DATA_DIR)
        free_gb = du.free / 1e9
        pct = 100 * du.used / du.total
        st = "error" if free_gb < 1 else "warn" if free_gb < 5 or pct > 90 else "ok"
        out.append(_c("Espace disque", st, f"{free_gb:.1f} Go libres ({pct:.0f} % utilisé)",
                      "" if st == "ok" else "libère de la place ou agrandis le disque du conteneur"))
    except OSError:
        pass
    size = DB_PATH.stat().st_size / 1e6 if DB_PATH.exists() else 0
    out.append(_c("Base de données", "ok", f"{size:.1f} Mo"))
    last = backup.list_all()
    if not last:
        out.append(_c("Sauvegarde", "warn", "aucune sauvegarde", "Réglages → Sauvegarde → Sauvegarder maintenant"))
    else:
        age = (time.time() - last[0]["created_at"]) / 3600
        out.append(_c("Sauvegarde", "ok" if age < 30 else "warn",
                      f"dernière il y a {age:.0f} h · {len(last)} copie(s)", "" if age < 30 else "vérifie les logs de sauvegarde"))
    out.append(_c("Lecture des scans (OCR)", "ok" if ocr.pdf_available() else "warn",
                  f"Tesseract ({ocr.LANGS})" if ocr.pdf_available() else "absent : PDF scannés et images illisibles",
                  "" if ocr.pdf_available() else "./update.sh (reconstruit l'image avec Tesseract)"))
    cols = library.list_collections()
    errs = [c["name"] for c in cols if c["status"] == "error"]
    out.append(_c("Bibliothèque", "warn" if errs else "ok",
                  f"{len(cols)} collection(s), {sum(c['chunks'] for c in cols)} passages"
                  + (f" · en erreur : {', '.join(errs)}" if errs else ""), "Bibliothèque → voir le message d'erreur" if errs else ""))
    return out


async def report() -> dict:
    checks: list[dict] = []
    checks += await _ollama()
    tasks = []
    if search.enabled():
        tasks.append(_http("Recherche web (SearXNG)", SEARXNG_URL, "/healthz", "docker compose logs searxng"))
    if NTFY_URL:
        tasks.append(_http("Notifications (ntfy)", NTFY_URL, "/v1/health", "docker compose logs ntfy"))
    tasks += [_telegram(), _remote()]
    checks += list(await asyncio.gather(*tasks))
    if not search.enabled():
        checks.append(_c("Recherche web (SearXNG)", "off", "désactivée"))
    checks += _storage()
    worst = "error" if any(c["status"] == "error" for c in checks) else "warn" if any(c["status"] == "warn" for c in checks) else "ok"
    return {"version": VERSION, "status": worst, "checks": checks, "time": time.time()}
