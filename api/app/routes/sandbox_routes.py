"""Routes : bac à sable (tests dans un conteneur jetable)."""
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


from ..streaming import event  # noqa: E402



class SandboxCmd(BaseModel):
    command: str = Field(default="", max_length=500)


class SandboxRun(BaseModel):
    command: str | None = Field(default=None, max_length=500)
    run_id: str | None = Field(default=None, max_length=32)   # tester les modifications d'une tâche de l'agent


@router.get("/api/sandbox/{cid}")
def sandbox_info(cid: int):
    with db.conn() as c:
        files = [r["path"] for r in c.execute("SELECT path FROM documents WHERE collection_id = ?", (cid,))]
    col = library.get_collection(cid)
    if col and col["kind"] == "code":   # les fichiers de projet (go.mod, Cargo.toml…) ne sont pas tous indexés
        root = library._code_root(col)
        if root.is_dir():
            files += [p.name for p in root.iterdir() if p.is_file()]
    return {**sandbox.status(), "command": sandbox.default_command(cid, files), "lang": sandbox.detect(files)}


@router.put("/api/sandbox/{cid}")
def sandbox_set(cid: int, body: SandboxCmd):
    sandbox.set_command(cid, body.command)
    return sandbox_info(cid)


@router.post("/api/sandbox/{cid}/run")
async def sandbox_run(cid: int, body: SandboxRun):
    overlay = None
    if body.run_id:
        r = agentcode.get_run(body.run_id)
        overlay = {k: v[1] for k, v in (r or {}).get("files", {}).items()} if r else None
    return StreamingResponse((event(**ev) async for ev in sandbox.run(cid, body.command, overlay)),
                             media_type="application/x-ndjson")
