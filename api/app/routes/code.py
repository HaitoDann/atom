"""Routes : mode Code : modifications proposées."""
from __future__ import annotations

import asyncio, base64, io, json, time  # noqa: F401
from typing import AsyncIterator  # noqa: F401

import httpx  # noqa: F401
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import codeedit
import logging

log = logging.getLogger("atom.code")

router = APIRouter()



class ProposeIn(BaseModel):
    path: str = Field(max_length=500)
    instruction: str = Field(min_length=2, max_length=4000)
    start: int | None = None
    end: int | None = None
    engine: str = "local"


@router.post("/api/code/{cid}/propose")
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
        log.warning("code : erreur gérée", exc_info=True)
        raise HTTPException(502, f"Le modèle n'a pas répondu : {e}") from e


@router.post("/api/code/proposals/{pid}/apply")
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


@router.get("/api/code/{cid}/changes")
def code_changes(cid: int):
    try:
        return codeedit.changes(cid)
    except FileNotFoundError as e:
        raise HTTPException(404, "Projet introuvable") from e


class RevertIn(BaseModel):
    path: str = Field(max_length=500)


@router.post("/api/code/{cid}/revert")
def code_revert(cid: int, body: RevertIn):
    try:
        codeedit.revert(cid, body.path)
    except FileNotFoundError as e:
        raise HTTPException(404, "Fichier introuvable") from e
    except (PermissionError, RuntimeError) as e:
        raise HTTPException(409, str(e)) from e
    return {"ok": True}
