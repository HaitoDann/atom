"""Observabilité : identifiant de requête, journaux structurés, métriques au format Prometheus.

- Chaque requête reçoit un identifiant (en-tête X-Request-ID, repris s'il est fourni) présent dans tous ses journaux.
- ATOM_LOG_FORMAT=json : journaux en JSON, une ligne par événement (pratique pour Loki, Grafana, jq…).
- /api/metrics : requêtes HTTP (nombre, durée, statut), appels aux modèles (tokens, erreurs, bascules),
  quotas et santé des fournisseurs. Accessible avec la session de l'interface, ou avec
  « Authorization: Bearer <ATOM_METRICS_TOKEN> » pour un serveur Prometheus.
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import re
import secrets
import time
from collections import defaultdict

request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
STARTED = time.time()
METRICS_TOKEN = os.getenv("ATOM_METRICS_TOKEN", "")
BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60)

# ---------------------------------------------------------------- journaux

_STD = set(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {"message", "asctime", "request_id"}


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {"ts": round(record.created, 3), "level": record.levelname.lower(), "logger": record.name,
               "msg": record.getMessage(), "request_id": getattr(record, "request_id", "-")}
        for k, v in vars(record).items():
            if k not in _STD and not k.startswith("_"):
                out[k] = v if isinstance(v, (str, int, float, bool, type(None))) else str(v)
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False)


def setup_logging() -> None:
    root = logging.getLogger()
    f = RequestIdFilter()
    json_mode = os.getenv("ATOM_LOG_FORMAT", "").lower() == "json"
    for h in root.handlers:
        h.addFilter(f)
        if json_mode:
            h.setFormatter(JsonFormatter())
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        for h in logging.getLogger(name).handlers:
            h.addFilter(f)
            if json_mode:
                h.setFormatter(JsonFormatter())


# ---------------------------------------------------------------- métriques HTTP

_requests: dict[tuple[str, str, int], int] = defaultdict(int)
_durations: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0] + [0] * len(BUCKETS))   # somme, nombre, seaux
_in_flight = 0
access_log = logging.getLogger("atom.access")


def _route(request) -> str:
    r = request.scope.get("route")
    path = getattr(r, "path", None)
    if path:
        return path
    p = request.url.path
    return "/api/…" if p.startswith("/api/") else "statique"


async def middleware(request, call_next):
    global _in_flight
    rid = request.headers.get("x-request-id", "")
    rid = rid if re.fullmatch(r"[\w.-]{1,64}", rid) else secrets.token_hex(6)
    token = request_id.set(rid)
    _in_flight += 1
    t0 = time.perf_counter()
    status = 500
    try:
        resp = await call_next(request)
        status = resp.status_code
        resp.headers["X-Request-ID"] = rid
        return resp
    finally:
        dt = time.perf_counter() - t0
        _in_flight -= 1
        route = _route(request)
        _requests[(request.method, route, status)] += 1
        d = _durations[(request.method, route)]
        d[0] += dt; d[1] += 1
        for i, b in enumerate(BUCKETS):
            if dt <= b:
                d[2 + i] += 1
        if request.url.path.startswith("/api/") and route != "/api/metrics":
            access_log.info("%s %s → %d (%.0f ms)", request.method, request.url.path, status, dt * 1000,
                            extra={"event": "http", "method": request.method, "route": route, "status": status,
                                   "duration_ms": round(dt * 1000, 1)})
        request_id.reset(token)


def token_ok(header: str | None) -> bool:
    if not METRICS_TOKEN or not header or not header.lower().startswith("bearer "):
        return False
    return secrets.compare_digest(header[7:].strip(), METRICS_TOKEN)


# ---------------------------------------------------------------- export Prometheus


def _esc(v) -> str:
    return str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _labels(**kw) -> str:
    return "{" + ",".join(f'{k}="{_esc(v)}"' for k, v in kw.items()) + "}" if kw else ""


def render() -> str:
    from . import db, providers, usage
    from .config import DB_PATH

    lines: list[str] = []

    def metric(name: str, kind: str, help_: str, samples: list[tuple[dict, float]]) -> None:
        lines.append(f"# HELP {name} {help_}")
        lines.append(f"# TYPE {name} {kind}")
        for labels, v in samples:
            lines.append(f"{name}{_labels(**labels)} {v}")

    metric("atom_info", "gauge", "Version d'Atom.", [({"version": os.getenv("ATOM_VERSION", "dev")}, 1)])
    metric("atom_uptime_seconds", "gauge", "Temps depuis le démarrage.", [({}, round(time.time() - STARTED, 1))])
    metric("atom_http_in_flight", "gauge", "Requêtes en cours.", [({}, _in_flight)])
    metric("atom_http_requests_total", "counter", "Requêtes HTTP par route et statut.",
           [({"method": m, "route": r, "status": s}, n) for (m, r, s), n in sorted(_requests.items())])
    lines.append("# HELP atom_http_request_duration_seconds Durée des requêtes HTTP.")
    lines.append("# TYPE atom_http_request_duration_seconds histogram")
    for (m, r), d in sorted(_durations.items()):
        cum = 0
        for i, b in enumerate(BUCKETS):
            cum = d[2 + i]
            lines.append(f"atom_http_request_duration_seconds_bucket{_labels(method=m, route=r, le=b)} {cum}")
        lines.append(f"atom_http_request_duration_seconds_bucket{_labels(method=m, route=r, le='+Inf')} {d[1]}")
        lines.append(f"atom_http_request_duration_seconds_sum{_labels(method=m, route=r)} {round(d[0], 4)}")
        lines.append(f"atom_http_request_duration_seconds_count{_labels(method=m, route=r)} {d[1]}")

    tot = usage.totals()
    metric("atom_model_calls_total", "counter", "Appels aux modèles (local et API).",
           [({"provider": p, "result": "ok"}, t["calls"] - (t["errors"] or 0)) for p, t in tot.items()]
           + [({"provider": p, "result": "error"}, t["errors"] or 0) for p, t in tot.items()])
    metric("atom_model_tokens_total", "counter", "Tokens consommés.",
           [({"provider": p, "kind": "prompt"}, t["prompt_tokens"] or 0) for p, t in tot.items()]
           + [({"provider": p, "kind": "completion"}, t["completion_tokens"] or 0) for p, t in tot.items()])
    metric("atom_model_seconds_total", "counter", "Temps passé à générer (appels réussis).",
           [({"provider": p}, round(t["seconds"] or 0, 2)) for p, t in tot.items()])
    metric("atom_model_fallback_total", "counter", "Réponses obtenues après une bascule automatique.",
           [({"provider": p}, t["rescues"] or 0) for p, t in tot.items()])
    metric("atom_model_cost_dollars_total", "counter", "Coût estimé (tarifs ATOM_<ID>_PRICE_IN/OUT).",
           [({"provider": p}, round(usage.cost(p, t["prompt_tokens"], t["completion_tokens"]), 6)) for p, t in tot.items()])

    prov = providers.ALL
    metric("atom_provider_quota_remaining", "gauge", "Requêtes restantes aujourd'hui.",
           [({"provider": p.id}, providers.quota_left(p.id)) for p in prov])
    metric("atom_provider_quota_limit", "gauge", "Quota quotidien.", [({"provider": p.id}, p.limit) for p in prov])
    metric("atom_provider_paused", "gauge", "1 si le fournisseur est en pause après une erreur.",
           [({"provider": p.id}, int(providers.describe(p)["paused"])) for p in prov])
    health = {p.id: providers.describe(p)["health"] for p in prov}
    metric("atom_provider_success_ratio", "gauge", "Réussite des 20 derniers appels.",
           [({"provider": pid}, h["success"] / 100) for pid, h in health.items() if h.get("success") is not None])
    metric("atom_provider_latency_seconds", "gauge", "Délai moyen avant le premier mot.",
           [({"provider": pid}, h["latency"]) for pid, h in health.items() if h.get("latency")])
    try:
        size = DB_PATH.stat().st_size
    except OSError:
        size = 0
    metric("atom_db_size_bytes", "gauge", "Taille de la base SQLite.", [({}, size)])
    with db.conn() as c:
        counts = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("conversations", "messages", "memories")}
    metric("atom_rows", "gauge", "Lignes par table.", [({"table": t}, n) for t, n in counts.items()])
    return "\n".join(lines) + "\n"
