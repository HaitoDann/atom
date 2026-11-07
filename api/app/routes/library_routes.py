"""Routes : bibliothèque."""
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



class CollectionIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = Field(default="docs", pattern="^(docs|code)$")
    source: str | None = Field(default=None, max_length=500)


@router.get("/api/library")
def get_library():
    from ..config import PROJECTS_DIR
    return {"collections": library.list_collections(), "server_projects": library.list_server_projects(),
            "projects_dir": str(PROJECTS_DIR)}


@router.post("/api/library/collections")
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


@router.patch("/api/library/collections/{cid}")
def patch_collection(cid: int, body: CollectionIn):
    library.rename_collection(cid, body.name.strip())
    return {"ok": True}


@router.delete("/api/library/collections/{cid}")
def remove_collection(cid: int):
    library.delete_collection(cid)
    return {"ok": True}


@router.post("/api/library/collections/{cid}/sync")
async def sync_collection(cid: int):
    col = library.get_collection(cid)
    if not col or col["kind"] != "code":
        raise HTTPException(404, "Projet introuvable")
    background(library.index_project(cid))
    return {"ok": True}


@router.get("/api/library/collections/{cid}/documents")
def collection_documents(cid: int):
    col = library.get_collection(cid)
    if not col:
        raise HTTPException(404, "Collection introuvable")
    return {"collection": col, "documents": library.list_documents(cid),
            "tree": library.tree(cid) if col["kind"] == "code" else None}


@router.post("/api/library/collections/{cid}/documents")
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


@router.get("/api/library/documents/{did}")
def document_detail(did: int):
    d = library.get_document(did)
    if not d:
        raise HTTPException(404, "Document introuvable")
    return {"document": d, "chunks": library.document_chunks(did)}


@router.get("/api/library/documents/{did}/file")
def document_file(did: int):
    d = library.get_document(did)
    if not d or not d.get("path") or not str(d["path"]).startswith(str(library.FILES_DIR)):
        raise HTTPException(404, "Fichier introuvable")
    return FileResponse(d["path"], filename=d["name"])


@router.delete("/api/library/documents/{did}")
def remove_document(did: int):
    library.delete_document(did)
    return {"ok": True}


@router.post("/api/library/documents/{did}/reindex")
async def reindex_document(did: int):
    if not library.get_document(did):
        raise HTTPException(404, "Document introuvable")
    background(library.index_document(did))
    return {"ok": True}


@router.get("/api/library/collections/{cid}/grep")
def project_grep(cid: int, q: str):
    """Recherche texte dans un projet de code : [{path, line, text}]."""
    q = q.strip()
    if len(q) < 2:
        return {"matches": []}
    try:
        return {"matches": library.grep(cid, q)}
    except FileNotFoundError as e:
        raise HTTPException(404, "Projet introuvable") from e


@router.get("/api/library/collections/{cid}/file")
def project_file(cid: int, path: str):
    try:
        return {"path": path, "content": library.read_file(cid, path)}
    except FileNotFoundError as e:
        raise HTTPException(404, "Fichier introuvable") from e
