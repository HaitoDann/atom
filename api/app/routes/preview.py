"""Aperçu des pages HTML produites par Atom (bouton « Aperçu » sur un bloc de code).

La page est servie avec la directive CSP « sandbox » : elle s'exécute dans une origine opaque, isolée d'Atom
(pas d'accès à la session, aux cookies ni à l'API), tout en gardant ses scripts, styles et polices.
Les aperçus sont gardés en mémoire 1 heure, au plus 50.
"""
from __future__ import annotations

import secrets
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

router = APIRouter()
TTL = 3600
MAX = 50
_store: dict[str, tuple[float, str]] = {}

SANDBOX_CSP = ("sandbox allow-scripts allow-forms allow-popups allow-modals; default-src * data: blob: 'unsafe-inline' "
               "'unsafe-eval'; frame-ancestors 'self'")


class PreviewIn(BaseModel):
    html: str = Field(min_length=1, max_length=2_000_000)


def _prune() -> None:
    now = time.time()
    for k in [k for k, (t, _) in _store.items() if now - t > TTL]:
        _store.pop(k, None)
    while len(_store) > MAX:
        _store.pop(min(_store, key=lambda k: _store[k][0]), None)


@router.post("/api/preview")
def create_preview(body: PreviewIn):
    _prune()
    pid = secrets.token_urlsafe(12)
    _store[pid] = (time.time(), body.html)
    return {"id": pid, "url": f"/api/preview/{pid}"}


@router.get("/api/preview/{pid}")
def show_preview(pid: str):
    item = _store.get(pid)
    if not item or time.time() - item[0] > TTL:
        raise HTTPException(404, "Aperçu expiré : relance-le depuis la réponse.")
    return HTMLResponse(item[1], headers={"Content-Security-Policy": SANDBOX_CSP, "X-Frame-Options": "SAMEORIGIN",
                                          "Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
