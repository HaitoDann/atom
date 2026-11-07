"""Routes : mode agent (Code)."""
from __future__ import annotations


from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import agentcode, library
from ..jobs import background

router = APIRouter()



class AgentIn(BaseModel):
    task: str = Field(min_length=3, max_length=4000)
    engine: str = Field(default="remote", pattern="^(remote|local)$")
    parent: str | None = Field(default=None, max_length=32, pattern="^[0-9a-f]{16}$")
    readonly: bool = False


@router.post("/api/agent/{cid}")
async def agent_start(cid: int, body: AgentIn):
    """Lance l'agent en arrière-plan : il continue même si la page est rechargée ou fermée."""
    if not library.get_collection(cid):
        raise HTTPException(404, "Projet introuvable")
    return {"id": agentcode.start(cid, body.task, body.engine, body.parent, body.readonly)}


class RulesIn(BaseModel):
    rules: list[str] = Field(default_factory=list, max_length=40)


@router.get("/api/agent/{cid}/rules")
def agent_rules(cid: int):
    return {"rules": agentcode.get_rules(cid)}


@router.put("/api/agent/{cid}/rules")
def agent_rules_put(cid: int, body: RulesIn):
    return {"rules": agentcode.set_rules(cid, body.rules)}


@router.get("/api/agent/{cid}/runs")
def agent_runs(cid: int):
    return {"runs": agentcode.list_runs(cid)}


@router.get("/api/agent/runs/{rid}")
def agent_get(rid: str, after: int = 0):
    r = agentcode.get_run(rid)
    if not r:
        raise HTTPException(404, "Tâche introuvable")
    return {"id": rid, "collection_id": r["collection_id"], "task": r["task"], "status": r["status"], "parent": r["parent"],
            "created_at": r["created_at"], "events": r["events"][after:], "total": len(r["events"])}


@router.post("/api/agent/runs/{rid}/stop")
def agent_stop(rid: str):
    agentcode.stop(rid)
    return {"ok": True}


@router.delete("/api/agent/runs/{rid}")
def agent_delete(rid: str):
    agentcode.stop(rid)
    agentcode.delete_run(rid)
    return {"ok": True}


class AgentApplyIn(BaseModel):
    paths: list[str] = Field(default_factory=list, max_length=500)


@router.post("/api/agent/runs/{rid}/apply")
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
