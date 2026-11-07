"""Routes : consommation des modèles en direct, routage intelligent et préférences."""
from __future__ import annotations

import asyncio
import time
from typing import AsyncIterator

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .. import alerts, hybrid, providers, usage
from ..streaming import event

router = APIRouter()


def _providers_view() -> list[dict]:
    """Chaque fournisseur avec son état, son quota et son classement actuel pour chaque type de demande."""
    out = []
    ranks = {t: {r["provider"].id: (i + 1, r["why"]) for i, r in enumerate(providers.plan(task=t))} for t in providers.TASKS}
    for p in providers.ALL:
        d = providers.describe(p)
        d["budget"] = providers.budget(p)
        d["quota_left"] = providers.quota_left(p.id)
        d["ranks"] = {t: ranks[t].get(p.id, (None, []))[0] for t in providers.TASKS}
        d["price"] = dict(zip(("in", "out"), usage.price(p.id), strict=True))
        out.append(d)
    return out


def grafana_enabled() -> bool:
    from ..grafana import enabled
    return enabled()


def snapshot(days: float = 1) -> dict:
    return {
        "at": time.time(),
        "summary": usage.summary(days),
        "providers": _providers_view(),
        "timeline": usage.timeline(24),
        "recent": usage.recent(40),
        "prefs": providers.route_prefs(),
        "tasks": list(providers.TASKS),
        "mode": hybrid.settings()["mode"],
        "alerts": alerts.status(),
        "grafana": grafana_enabled(),
    }


@router.get("/api/usage")
def get_usage(days: float = Query(default=1, ge=0.04, le=90)):
    return snapshot(days)


@router.get("/api/usage/live")
async def usage_live():
    """Flux NDJSON : un état complet, puis chaque appel au moment où il se termine (et un état frais toutes les 20 s)."""
    async def gen() -> AsyncIterator[bytes]:
        q = usage.subscribe()
        try:
            yield event(type="snapshot", **snapshot())
            last = time.time()
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=20)
                    yield event(**ev)
                except asyncio.TimeoutError:
                    pass
                if time.time() - last >= 20:
                    yield event(type="snapshot", **snapshot())
                    last = time.time()
        finally:
            usage.unsubscribe(q)
    return StreamingResponse(gen(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache"})


class RoutingIn(BaseModel):
    prefs: dict[str, str] = Field(default_factory=dict)


@router.put("/api/usage/routing")
def put_routing(body: RoutingIn):
    return {"prefs": providers.set_route_prefs(body.prefs)}


class RouteIn(BaseModel):
    message: str = Field(max_length=20000)
    sensitive: bool = False


@router.post("/api/usage/route")
def preview_route(body: RouteIn):
    """« Quel modèle répondrait à ce message, et pourquoi ? » — sans rien envoyer."""
    task = hybrid.classify(body.message)
    msgs = [{"role": "user", "content": body.message}]
    est = providers.estimate_tokens(msgs)
    if task != "code" and est > 6000:
        task = "long"
    engine, reason = hybrid.decide("default", body.message, needs_memory=body.sensitive, needs_docs=False)
    rows = providers.plan(hybrid.settings()["provider"] or None, body.sensitive, task=task, est_tokens=est)
    return {"task": task, "est_tokens": est, "engine": engine, "reason": reason,
            "order": [{"id": r["provider"].id, "name": r["provider"].name, "model": providers.model_of(r["provider"]),
                       "score": r["score"], "why": r["why"]} for r in rows]}


@router.post("/api/alerts/test")
async def test_alert():
    """Envoie une notification d'essai sur les canaux configurés (ntfy, Telegram)."""
    from .. import notify
    ok = await notify.send("Test d'alerte Atom", "Les alertes de consommation arriveront ici.", tags="bell")
    return {"sent": ok, "channels": notify.enabled()}


@router.post("/api/alerts/check")
async def run_alert_check():
    return {"sent": await alerts.check(), "status": alerts.status()}


@router.get("/api/monitoring")
def monitoring():
    """Grafana est-il servi à travers Atom ? (vue « Tableau de bord »)"""
    return {"grafana": grafana_enabled(), "path": "/grafana/d/atom/atom"}


@router.get("/api/monitoring/check")
async def monitoring_check():
    """Vérifie chaque panneau du tableau Grafana (erreurs exactes, panneaux encore vides)."""
    from .. import grafana
    return await grafana.check()
