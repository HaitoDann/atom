"""Routes Git des projets de code."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import gitops, library
from ..jobs import background

router = APIRouter()


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


@router.get("/api/git/{cid}/status")
def git_status(cid: int):
    return _git_call(gitops.status, cid)


@router.get("/api/git/{cid}/diff")
def git_diff(cid: int):
    return {"diff": _git_call(gitops.diff, cid, None)}


@router.post("/api/git/{cid}/branch")
def git_branch(cid: int, body: GitName):
    return _git_call(gitops.new_branch, cid, body.name)


@router.post("/api/git/{cid}/switch")
async def git_switch(cid: int, body: GitName):
    out = _git_call(gitops.switch, cid, body.name)
    background(library.index_project(cid))   # les fichiers ont changé : réindexation (seuls les fichiers modifiés)
    return out


@router.post("/api/git/{cid}/commit")
def git_commit(cid: int, body: GitCommit):
    return _git_call(gitops.commit, cid, body.message, body.paths)


@router.post("/api/git/{cid}/push")
def git_push(cid: int):
    return _git_call(gitops.push, cid)


@router.post("/api/git/{cid}/discard")
async def git_discard(cid: int):
    out = _git_call(gitops.discard_all, cid)
    background(library.index_project(cid))
    return out


@router.post("/api/git/{cid}/message")
async def git_message(cid: int, body: GitPaths):
    try:
        return {"message": await gitops.suggest_message(cid, body.paths)}
    except (FileNotFoundError, PermissionError, ValueError, gitops.GitError) as e:
        raise HTTPException(409, str(e)) from e
