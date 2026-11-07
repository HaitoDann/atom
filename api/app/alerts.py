"""Alertes de consommation : Atom te prévient (ntfy / Telegram) avant que ça coince.

Vérifié chaque minute, à partir du journal des appels (usage.py) et des quotas :
- quota d'un fournisseur utilisé à ATOM_ALERT_QUOTA (80 % par défaut) — une fois par fournisseur et par jour ;
- fournisseurs distants tous en échec depuis 15 min (Atom répond alors en local) — au plus une fois toutes les 2 h ;
- budget mensuel ATOM_COST_BUDGET (en dollars) atteint à 80 % puis à 100 % — une fois par palier et par mois.
Les alertes envoyées sont gardées (les 50 dernières) et affichées dans Réglages → Consommation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime

from . import db

log = logging.getLogger("atom.alerts")
INTERVAL = 60
DOWN_WINDOW = 15 * 60
DOWN_COOLDOWN = 2 * 3600


def quota_threshold() -> float:
    try:
        return min(1.0, max(0.1, float(os.getenv("ATOM_ALERT_QUOTA", "0.8"))))
    except ValueError:
        return 0.8


def budget() -> float:
    try:
        return max(0.0, float(os.getenv("ATOM_COST_BUDGET", "0") or 0))
    except ValueError:
        return 0.0


def _sent() -> dict:
    try:
        return json.loads(db.kv_get("alerts:sent") or "{}")
    except ValueError:
        return {}


def history() -> list[dict]:
    try:
        return json.loads(db.kv_get("alerts:log") or "[]")
    except ValueError:
        return []


def _remember(key: str, kind: str, title: str, body: str) -> None:
    sent = _sent()
    sent[key] = time.time()
    db.kv_set("alerts:sent", json.dumps({k: v for k, v in sent.items() if time.time() - v < 40 * 86400}))
    db.kv_set("alerts:log", json.dumps(([{"at": time.time(), "kind": kind, "title": title, "body": body}] + history())[:50]))
    counts = counts_by_kind()
    counts[kind] = counts.get(kind, 0) + 1
    db.kv_set("alerts:counts", json.dumps(counts))


def counts_by_kind() -> dict[str, int]:
    """Alertes envoyées depuis le début, par type (compteur exposé dans /api/metrics)."""
    try:
        return json.loads(db.kv_get("alerts:counts") or "{}")
    except ValueError:
        return {}


def month_cost() -> float:
    from . import usage
    start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()
    with db.conn() as c:
        rows = c.execute("SELECT provider, SUM(COALESCE(prompt_tokens, 0)) AS p, SUM(COALESCE(completion_tokens, 0)) AS o "
                         "FROM api_usage WHERE ts >= ? GROUP BY provider", (start,)).fetchall()
    return sum(usage.cost(r["provider"], r["p"], r["o"]) for r in rows)


def pending() -> list[tuple[str, str, str, str]]:
    """Alertes à envoyer maintenant : [(clé anti-répétition, type, titre, message)]."""
    from . import providers
    out = []
    sent = _sent()
    today = datetime.now().strftime("%Y-%m-%d")
    th = quota_threshold()
    for p in providers.ALL:
        if not p.configured or not p.limit:
            continue
        used = providers.used_today(p.id)
        key = f"quota:{p.id}:{today}"
        if used >= th * p.limit and key not in sent:
            out.append((key, "quota", f"Quota {p.name} à {round(100 * used / p.limit)} %",
                        f"{used} requêtes sur {p.limit} aujourd'hui. Atom basculera sur les autres fournisseurs, "
                        "puis sur le modèle local, une fois le quota atteint."))

    since = time.time() - DOWN_WINDOW
    with db.conn() as c:
        r = c.execute("SELECT COUNT(*) AS n, SUM(ok) AS ok, GROUP_CONCAT(DISTINCT provider) AS who FROM api_usage "
                      "WHERE ts >= ? AND provider != 'local' AND COALESCE(task, '') != 'agent'", (since,)).fetchone()
    if r["n"] and r["n"] >= 3 and not r["ok"] and time.time() - sent.get("down", 0) >= DOWN_COOLDOWN:
        out.append(("down", "down", "Fournisseurs distants en panne",
                    f"{r['n']} appels en échec depuis 15 minutes ({r['who']}). Atom répond avec le modèle local ; "
                    "détails dans Réglages → Consommation."))

    b = budget()
    if b:
        cost, month = month_cost(), datetime.now().strftime("%Y-%m")
        for pct in (100, 80):
            key = f"budget:{pct}:{month}"
            if cost >= b * pct / 100:
                if key not in sent:
                    out.append((key, "budget", f"Budget API {'dépassé' if pct == 100 else 'à 80 %'}",
                                f"{cost:.2f} $ dépensés ce mois-ci sur un budget de {b:.2f} $."))
                break
    return out


async def check() -> list[dict]:
    from . import notify
    sent = []
    for key, kind, title, body in pending():
        _remember(key, kind, title, body)
        await notify.send(title, body, tags={"quota": "chart_with_upwards_trend", "down": "warning",
                                             "budget": "moneybag"}.get(kind, "bell"))
        log.warning("alerte : %s — %s", title, body, extra={"event": "alert", "kind": kind})
        sent.append({"kind": kind, "title": title})
    return sent


async def scheduler() -> None:
    while True:
        await asyncio.sleep(INTERVAL)
        try:
            await check()
        except Exception:
            log.exception("vérification des alertes impossible")


def status() -> dict:
    return {"quota_threshold": quota_threshold(), "budget": budget(), "month_cost": round(month_cost(), 4),
            "history": history()[:20]}
