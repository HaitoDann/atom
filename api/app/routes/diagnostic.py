"""Diagnostic complet en un clic (Réglages → État) : services, fournisseurs, tableau Grafana, copie sur le NAS, atelier.

Produit un rapport lisible et copiable, sans aucun secret : on peut le coller tel quel pour demander de l'aide.
Seules actions réelles : un test de restauration de la copie NAS la plus récente (lecture seule) et les appels
minimaux de vérification des fournisseurs (déjà faits par l'écran État, mis en cache 30 min).
"""
from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter

from .. import grafana, health, offsite, workshop

router = APIRouter()
ICON = {"ok": "✅", "warn": "⚠️", "error": "❌", "off": "➖"}


async def _grafana() -> dict:
    if not grafana.enabled():
        return {"name": "Tableau de bord Grafana", "status": "off", "detail": "non activé (docker-compose.monitoring.yml)"}
    r = await grafana.check()
    if r["ok"]:
        empty = f" · {len(r.get('empty', []))} encore vide(s)" if r.get("empty") else ""
        return {"name": "Tableau de bord Grafana", "status": "ok", "detail": f"{r['checked']} panneaux sans erreur{empty}"}
    errs = "; ".join(f"{e['panel']} : {e['error'][:120]}" for e in r["errors"][:6])
    return {"name": "Tableau de bord Grafana", "status": "error", "detail": f"{len(r['errors'])} erreur(s) — {errs}"}


async def _nas() -> dict:
    st = offsite.status()
    name = f"Copie sur {st['target']}"
    if not st["configured"]:
        return {"name": name, "status": "off", "detail": "non configurée (README → Sauvegarde sur un NAS)"}
    if not st["reachable"]:
        return {"name": name, "status": "error", "detail": f"{st['dir']} non monté ou en lecture seule"}
    if not st["count"]:
        return {"name": name, "status": "warn", "detail": "joignable mais aucune copie : Réglages → Sauvegarde → Envoyer maintenant"}
    try:
        v = await asyncio.to_thread(offsite.verify)
        c = v["counts"]
        return {"name": name, "status": "ok",
                "detail": f"{st['count']} copie(s) ; restauration testée : {c['messages']} messages, {c['memories']} souvenirs"}
    except Exception as e:  # noqa: BLE001 — le rapport doit aller au bout
        return {"name": name, "status": "error", "detail": f"test de restauration en échec : {e}"}


def _workshop() -> dict:
    try:
        p = workshop.preview("review", None, 1, "Crée une page web de présentation")
    except Exception as e:  # noqa: BLE001
        return {"name": "Atelier multi-IA", "status": "error", "detail": str(e)[:200]}
    team = " → ".join(f"{s['role']} ({s['engine']})" for s in p["steps"])
    local_only = not p["remote_calls"]
    return {"name": "Atelier multi-IA", "status": "warn" if local_only or p["warnings"] else "ok",
            "detail": ("tout en local : ajoute une clé d'API pour de meilleurs résultats · " if local_only else "") + team
            + (" · " + " ".join(p["warnings"]) if p["warnings"] else "")}


@router.post("/api/diagnostic")
async def diagnostic():
    t0 = time.time()
    rep, graf, nas = await asyncio.gather(health.report(), _grafana(), _nas())
    # La copie NAS de l'écran État est remplacée par la version du diagnostic (avec test de restauration).
    checks = [c for c in rep["checks"] if not c["name"].startswith("Copie sur")] + [graf, nas, _workshop()]
    worst = "error" if any(c["status"] == "error" for c in checks) else "warn" if any(c["status"] == "warn" for c in checks) else "ok"
    lines = [f"Diagnostic Atom {rep['version']} — {time.strftime('%d/%m/%Y %H:%M')} — "
             f"{ {'ok': 'tout fonctionne', 'warn': 'points à surveiller', 'error': 'problèmes détectés'}[worst]}"]
    lines += [f"{ICON.get(c['status'], '·')} {c['name']} : {c['detail']}" + (f" (conseil : {c['hint']})" if c.get("hint") and c["status"] != "ok" else "")
              for c in checks]
    return {"status": worst, "checks": checks, "report": "\n".join(lines), "seconds": round(time.time() - t0, 1)}
