"""Consommation des modèles : chaque appel (local ou API) est journalisé, agrégé et diffusé en direct.

- `record()` : appelé par providers.py (API) et llm.py (Ollama) à la fin de chaque appel, réussi ou non.
- `summary()` / `timeline()` / `recent()` : tableaux de bord (réglages → Consommation) et /api/metrics.
- `subscribe()` : flux en direct des appels, pour suivre les bascules au moment où elles arrivent.
- Coût estimé : ATOM_<ID>_PRICE_IN / ATOM_<ID>_PRICE_OUT en dollars par million de tokens (0 par défaut : offres gratuites).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime

from . import db

log = logging.getLogger("atom.usage")
RETENTION_DAYS = int(os.getenv("ATOM_USAGE_RETENTION_DAYS", "90"))

_subscribers: set[asyncio.Queue] = set()


def price(pid: str) -> tuple[float, float]:
    def f(k: str) -> float:
        try:
            return float(os.getenv(f"ATOM_{pid.upper()}_{k}", "0") or 0)
        except ValueError:
            return 0.0
    return f("PRICE_IN"), f("PRICE_OUT")


def cost(pid: str, prompt_tokens: int | None, completion_tokens: int | None) -> float:
    pin, pout = price(pid)
    return ((prompt_tokens or 0) * pin + (completion_tokens or 0) * pout) / 1_000_000


def record(provider: str, *, model: str = "", task: str | None = None, ok: bool = True, first_s: float | None = None,
           total_s: float | None = None, prompt_tokens: int | None = None, completion_tokens: int | None = None,
           error: str = "", reason: str = "", fallback_from: str | None = None) -> dict:
    """Journalise un appel et le diffuse aux abonnés. Ne lève jamais : le suivi ne doit pas casser une réponse."""
    ev = {"ts": time.time(), "provider": provider, "model": model, "task": task, "ok": ok,
          "first_s": _r(first_s), "total_s": _r(total_s), "prompt_tokens": prompt_tokens,
          "completion_tokens": completion_tokens, "error": (error or "")[:300], "reason": (reason or "")[:200],
          "fallback_from": fallback_from}
    try:
        with db.conn() as c:
            cur = c.execute(
                "INSERT INTO api_usage (ts, provider, model, task, ok, first_s, total_s, prompt_tokens, completion_tokens, "
                "error, reason, fallback_from) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ev["ts"], provider, model, task, int(ok), ev["first_s"], ev["total_s"], prompt_tokens, completion_tokens,
                 ev["error"], ev["reason"], fallback_from))
            ev["id"] = cur.lastrowid
    except Exception:
        log.warning("journal de consommation indisponible", exc_info=True)
    ev["cost"] = round(cost(provider, prompt_tokens, completion_tokens), 6)
    log.info("appel %s", provider, extra={"event": "model_call", **{k: v for k, v in ev.items() if v not in (None, "")}})
    for q in list(_subscribers):
        try:
            q.put_nowait({"type": "call", **ev})
        except asyncio.QueueFull:
            pass
    return ev


def _r(v: float | None) -> float | None:
    return round(v, 3) if v is not None else None


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    _subscribers.discard(q)


def _since(days: float) -> float:
    if days >= 1 and float(days).is_integer():
        midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        return midnight - (days - 1) * 86400
    return time.time() - days * 86400


def summary(days: float = 1) -> list[dict]:
    """Par fournisseur, depuis minuit (days=1) ou sur N jours : appels, réussite, tokens, latence, coût, bascules."""
    with db.conn() as c:
        rows = c.execute("""
            SELECT provider, COUNT(*) AS calls, SUM(ok) AS ok,
                   SUM(COALESCE(prompt_tokens, 0)) AS prompt_tokens, SUM(COALESCE(completion_tokens, 0)) AS completion_tokens,
                   AVG(CASE WHEN ok THEN first_s END) AS first_s, AVG(CASE WHEN ok THEN total_s END) AS total_s,
                   SUM(CASE WHEN fallback_from IS NOT NULL THEN 1 ELSE 0 END) AS rescues,
                   MAX(ts) AS last_ts
            FROM api_usage WHERE ts >= ? GROUP BY provider ORDER BY calls DESC""", (_since(days),)).fetchall()
        dropped = dict(c.execute(
            "SELECT provider, COUNT(*) FROM api_usage WHERE ts >= ? AND ok = 0 GROUP BY provider", (_since(days),)).fetchall())
    out = []
    for r in rows:
        d = dict(r)
        d["errors"] = dropped.get(d["provider"], 0)
        d["success"] = round(100 * (d["ok"] or 0) / d["calls"]) if d["calls"] else None
        d["first_s"] = _r(d["first_s"]); d["total_s"] = _r(d["total_s"])
        d["cost"] = round(cost(d["provider"], d["prompt_tokens"], d["completion_tokens"]), 4)
        out.append(d)
    return out


def timeline(hours: int = 24) -> list[dict]:
    """Tokens et appels par heure et par fournisseur (graphique de la journée)."""
    since = time.time() - hours * 3600
    with db.conn() as c:
        rows = c.execute("""
            SELECT CAST(ts / 3600 AS INTEGER) * 3600 AS hour, provider, COUNT(*) AS calls,
                   SUM(COALESCE(prompt_tokens, 0) + COALESCE(completion_tokens, 0)) AS tokens, SUM(1 - ok) AS errors
            FROM api_usage WHERE ts >= ? GROUP BY hour, provider ORDER BY hour""", (since,)).fetchall()
    return [dict(r) for r in rows]


def recent(limit: int = 50) -> list[dict]:
    with db.conn() as c:
        rows = c.execute("SELECT * FROM api_usage ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["ok"] = bool(d["ok"])
        d["cost"] = round(cost(d["provider"], d["prompt_tokens"], d["completion_tokens"]), 6)
        out.append(d)
    return out


def totals() -> dict:
    """Compteurs cumulés depuis le début (pour /api/metrics, format compteur Prometheus)."""
    with db.conn() as c:
        rows = c.execute("""
            SELECT provider, COUNT(*) AS calls, SUM(1 - ok) AS errors,
                   SUM(COALESCE(prompt_tokens, 0)) AS prompt_tokens, SUM(COALESCE(completion_tokens, 0)) AS completion_tokens,
                   SUM(CASE WHEN ok THEN COALESCE(total_s, 0) ELSE 0 END) AS seconds,
                   SUM(CASE WHEN fallback_from IS NOT NULL THEN 1 ELSE 0 END) AS rescues
            FROM api_usage GROUP BY provider""").fetchall()
    return {r["provider"]: dict(r) for r in rows}


def last_calls(provider: str, n: int = 20) -> list[dict]:
    """Derniers appels d'un fournisseur (pour reconstituer sa santé au démarrage)."""
    with db.conn() as c:
        rows = c.execute("SELECT ok, first_s, error FROM api_usage WHERE provider = ? ORDER BY id DESC LIMIT ?",
                         (provider, n)).fetchall()
    return [dict(r) for r in reversed(rows)]


def prune(max_days: int = RETENTION_DAYS) -> int:
    with db.conn() as c:
        return c.execute("DELETE FROM api_usage WHERE ts < ?", (time.time() - max_days * 86400,)).rowcount
