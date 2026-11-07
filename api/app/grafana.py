"""Grafana servi à travers Atom (/grafana/…), pour l'afficher dans l'interface sans ouvrir de port.

Grafana tourne dans le réseau Docker interne (docker-compose.monitoring.yml) avec un accès anonyme en lecture :
c'est Atom qui contrôle l'accès — seules les sessions connectées à Atom atteignent /grafana/.
Le cookie de session d'Atom n'est jamais transmis à Grafana.
"""

from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

log = logging.getLogger("atom.grafana")
router = APIRouter()

HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding",
       "upgrade", "host", "content-length"}
_client: httpx.AsyncClient | None = None


def url() -> str:
    return os.getenv("ATOM_GRAFANA_URL", "").rstrip("/")


def enabled() -> bool:
    return bool(url())


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(10, read=60), follow_redirects=False)
    return _client


def _cookies(raw: str) -> str:
    """Ne transmet que les cookies de Grafana (jamais la session d'Atom)."""
    keep = [c.strip() for c in raw.split(";") if c.strip().startswith("grafana")]
    return "; ".join(keep)


@router.api_route("/grafana/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
                  include_in_schema=False)
async def proxy(path: str, request: Request):
    if not enabled():
        return JSONResponse({"detail": "Grafana n'est pas activé (docker-compose.monitoring.yml)."}, status_code=404)
    target = f"{url()}/grafana/{path}" + (f"?{request.url.query}" if request.url.query else "")   # requête transmise telle quelle
    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP and k.lower() != "cookie"}
    gc = _cookies(request.headers.get("cookie", ""))
    if gc:
        headers["cookie"] = gc
    # Comme tout relais (nginx : proxy_set_header Host $host), on garde l'adresse vue par le navigateur :
    # Grafana compare l'en-tête Origin des requêtes POST (panneaux) à Host, et les refuse sinon (« origin not allowed »).
    headers["host"] = request.headers.get("host", "")
    headers["x-forwarded-host"] = request.headers.get("x-forwarded-host", request.headers.get("host", ""))
    headers["x-forwarded-proto"] = request.headers.get("x-forwarded-proto", request.url.scheme)
    req = _http().build_request(request.method, target, headers=headers,
                                content=await request.body())
    try:
        r = await _http().send(req, stream=True)
    except httpx.HTTPError as e:
        log.warning("Grafana injoignable : %s", e)
        return JSONResponse({"detail": f"Grafana injoignable ({e.__class__.__name__}) : docker compose ps grafana"},
                            status_code=502)
    out = [(k, v) for k, v in r.headers.multi_items() if k.lower() not in HOP]
    resp = StreamingResponse(r.aiter_raw(), status_code=r.status_code, background=BackgroundTask(r.aclose))
    resp.raw_headers = [(k.encode("latin-1"), v.encode("latin-1")) for k, v in out]
    return resp
