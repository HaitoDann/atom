"""Routes : sauvegardes."""
from __future__ import annotations

import asyncio, base64, io, json, time  # noqa: F401
from typing import AsyncIterator  # noqa: F401

import httpx  # noqa: F401
from fastapi import APIRouter, HTTPException, Request  # noqa: F401
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse  # noqa: F401
from pydantic import BaseModel, Field  # noqa: F401

from .. import agent, agentcode, analysis, auth, backup, canvas, codeedit, proxmox, research, sandbox, spaces, db, gitops, models_lab, ocr, providers, hybrid, library, llm, memory, notify, reminders, search, system, telegram, workshop  # noqa: F401
from ..config import DEFAULT_MODEL, DEFAULT_PERSONA, EMBED_MODEL, PROVIDER, WEB_DIR  # noqa: F401
from ..jobs import background  # noqa: F401

router = APIRouter()



@router.get("/api/backups")
def get_backups():
    from ..config import BACKUP_DIR, BACKUP_KEEP, BACKUP_TIME
    return {"backups": backup.list_all(), "dir": str(BACKUP_DIR), "keep": BACKUP_KEEP, "time": BACKUP_TIME}


@router.post("/api/backups")
def make_backup():
    return backup.create("manual")


@router.get("/api/backups/{name}/download")
def download_backup(name: str):
    try:
        p = backup.path_of(name)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(404, "Sauvegarde introuvable") from e
    return FileResponse(p, filename=name, media_type="application/octet-stream")


@router.post("/api/backups/{name}/restore")
def restore_backup(name: str):
    try:
        return backup.restore_file(backup.path_of(name))
    except FileNotFoundError as e:
        raise HTTPException(404, "Sauvegarde introuvable") from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/api/export")
def export_db():
    """Télécharge une copie fraîche de toute la mémoire d'Atom."""
    info = backup.create("export")
    return FileResponse(backup.path_of(info["name"]), filename=info["name"].replace("-export", ""),
                        media_type="application/octet-stream")


@router.post("/api/import")
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
