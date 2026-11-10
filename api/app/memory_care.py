"""Entretien de la mémoire : chaque semaine, Atom range ce qu'il sait de toi.

1. Doublons : deux souvenirs presque identiques → un seul (le plus sûr et le plus important est gardé).
2. Même sujet : le modèle local tranche (même info, complément → fusion, contradiction → l'ancien est archivé).
3. Faits temporaires arrivés à échéance (« prépare un examen en juin ») : Atom te demande s'ils sont encore vrais
   (boutons Garder / Oublier sur Telegram et dans l'interface) ; sans réponse 30 jours plus tard, ils sont archivés.
4. Anecdotes jamais utilisées depuis longtemps : archivées (importance 1, jamais rappelées, plus de N jours).
5. Résumé hebdomadaire : ce qu'Atom a retenu ces 7 derniers jours et ce qu'il a rangé, pour que tu corriges.

Rien n'est supprimé : les souvenirs écartés sont archivés (Réglages → Souvenirs → archivés) et restaurables.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

import numpy as np

from . import db, memory, notify
from .config import DUPLICATE_SCORE, RELATED_SCORE

log = logging.getLogger("atom.memory_care")

DEFAULTS = {"enabled": True, "weekday": 6, "time": "10:00", "summary": True, "stale_days": 180, "max_judge": 15}
FORGET_AFTER_DAYS = 30        # fait temporaire à revoir, sans réponse : archivé après ce délai


def settings() -> dict:
    s = dict(DEFAULTS)
    try:
        s.update({k: v for k, v in json.loads(db.kv_get("memory_care") or "{}").items() if k in DEFAULTS})
    except ValueError:
        pass
    return s


def save_settings(new: dict) -> dict:
    s = settings()
    s.update({k: v for k, v in new.items() if k in DEFAULTS and v is not None})
    s["weekday"] = max(0, min(6, int(s["weekday"])))
    s["stale_days"] = max(30, min(3650, int(s["stale_days"])))
    s["max_judge"] = max(0, min(100, int(s["max_judge"])))
    try:
        h, m = (int(x) for x in str(s["time"]).split(":"))
        s["time"] = f"{min(23, max(0, h)):02d}:{min(59, max(0, m)):02d}"
    except ValueError:
        s["time"] = DEFAULTS["time"]
    db.kv_set("memory_care", json.dumps(s))
    return s


def _keeper(a: dict, b: dict) -> tuple[dict, dict]:
    """(gardé, écarté) : le plus important, puis le plus sûr, puis le plus utilisé, puis le plus ancien."""
    def rank(f: dict) -> tuple:
        return (f.get("importance") or 2, f.get("confidence") or 0.8, f.get("hits") or 0, -(f.get("created_at") or 0))
    return (a, b) if rank(a) >= rank(b) else (b, a)


def _pairs(facts: list[dict], min_score: float) -> list[tuple[float, dict, dict]]:
    """Paires de souvenirs proches (similarité cosinus des embeddings), de la plus proche à la moins proche."""
    items = [f for f in facts if f.get("embedding") is not None]
    if len(items) < 2:
        return []
    dim = items[0]["embedding"].shape
    items = [f for f in items if f["embedding"].shape == dim]
    m = np.stack([f["embedding"] for f in items])
    sims = m @ m.T
    out = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if sims[i, j] >= min_score:
                out.append((float(sims[i, j]), items[i], items[j]))
    out.sort(key=lambda x: x[0], reverse=True)
    return out


async def run(dry: bool = False) -> dict:
    """Une passe d'entretien. dry=True : rapport de ce qui serait fait, sans rien changer."""
    s = settings()
    now = time.time()
    rep = {"at": now, "dry": dry, "merged": [], "contradictions": [], "stale": [], "to_review": [], "expired": [],
           "judged": 0}
    facts = db.list_memories()
    await memory._backfill(facts)
    facts = db.list_memories()
    gone: set[int] = set()

    # 1-2. Doublons et souvenirs du même sujet
    for score, a, b in _pairs(facts, RELATED_SCORE):
        if a["id"] in gone or b["id"] in gone:
            continue
        keep, drop = _keeper(a, b)
        if score >= DUPLICATE_SCORE:
            rep["merged"].append({"kept": keep["content"], "dropped": drop["content"]})
            if not dry:
                db.archive_memory(drop["id"], superseded_by=keep["id"])
                db.set_memory_fields(keep["id"], confidence=min(1.0, (keep.get("confidence") or 0.8) + 0.05))
            gone.add(drop["id"])
            continue
        if rep["judged"] >= s["max_judge"]:
            continue
        older, newer = (a, b) if (a.get("created_at") or 0) <= (b.get("created_at") or 0) else (b, a)
        rel = await memory._judge(older, newer["content"], None)
        rep["judged"] += 1
        if rel["relation"] == "identique":
            rep["merged"].append({"kept": keep["content"], "dropped": drop["content"]})
            if not dry:
                db.archive_memory(drop["id"], superseded_by=keep["id"])
            gone.add(drop["id"])
        elif rel["relation"] == "complement" and rel["fusion"].strip():
            fused = rel["fusion"].strip()[:300]
            rep["merged"].append({"kept": fused, "dropped": drop["content"], "fused": True})
            if not dry:
                from . import llm
                v = await llm.embed([fused])
                db.update_memory(keep["id"], fused, v[0] if v else keep["embedding"])
                db.archive_memory(drop["id"], superseded_by=keep["id"])
            gone.add(drop["id"])
        elif rel["relation"] == "contradiction":       # le plus récent l'emporte
            rep["contradictions"].append({"old": older["content"], "new": newer["content"]})
            if not dry:
                db.archive_memory(older["id"], superseded_by=newer["id"])
            gone.add(older["id"])

    # 3. Faits temporaires arrivés à échéance
    for f in facts:
        if f["id"] in gone or not f.get("review_at") or f["review_at"] > now:
            continue
        if f["review_at"] < now - FORGET_AFTER_DAYS * 86400:
            rep["expired"].append(f["content"])
            if not dry:
                db.archive_memory(f["id"])
            gone.add(f["id"])
        else:
            rep["to_review"].append({"id": f["id"], "content": f["content"]})

    # 4. Anecdotes jamais utilisées
    limit = now - s["stale_days"] * 86400
    for f in facts:
        if f["id"] in gone:
            continue
        if (f.get("importance") or 2) <= 1 and not f.get("hits") and (f.get("created_at") or now) < limit:
            rep["stale"].append(f["content"])
            if not dry:
                db.archive_memory(f["id"])
            gone.add(f["id"])

    rep["new_week"] = [f["content"] for f in facts if f["id"] not in gone and (f.get("created_at") or 0) > now - 7 * 86400]
    rep["active"] = len(facts) - len(gone)
    if not dry:
        db.kv_set("memory_care_last", json.dumps(rep, ensure_ascii=False))
    log.info("entretien de la mémoire%s : %d fusionnés, %d contradictions, %d anecdotes, %d périmés, %d à revoir",
             " (simulation)" if dry else "", len(rep["merged"]), len(rep["contradictions"]), len(rep["stale"]),
             len(rep["expired"]), len(rep["to_review"]))
    return rep


def last() -> dict:
    try:
        return json.loads(db.kv_get("memory_care_last") or "{}")
    except ValueError:
        return {}


def summary_text(rep: dict) -> str:
    """Résumé hebdomadaire lisible (Telegram, ntfy, conversation)."""
    lines = []
    if rep.get("new_week"):
        lines.append("**Retenu cette semaine**")
        lines += [f"- {x}" for x in rep["new_week"][:10]]
    tidy = []
    for m in rep.get("merged", [])[:5]:
        tidy.append(f"- {'Fusionné' if m.get('fused') else 'Doublon retiré'} : « {m['dropped']} » → « {m['kept']} »")
    for c in rep.get("contradictions", [])[:5]:
        tidy.append(f"- Mis à jour : « {c['old']} » → « {c['new']} »")
    for x in rep.get("stale", [])[:5]:
        tidy.append(f"- Anecdote jamais utilisée, archivée : « {x} »")
    for x in rep.get("expired", [])[:5]:
        tidy.append(f"- Temporaire et sans réponse, archivé : « {x} »")
    if tidy:
        lines += ["", "**Rangé**"] + tidy
    if rep.get("to_review"):
        lines += ["", "**Toujours vrai ?** (réponds avec les boutons)"] + [f"- {x['content']}" for x in rep["to_review"][:5]]
    lines += ["", f"{rep.get('active', 0)} souvenirs actifs. Rien n'est supprimé : tout est restaurable dans Réglages → Souvenirs."]
    return "\n".join(lines)


async def weekly(rep: dict | None = None) -> dict:
    """Entretien + résumé envoyé (et questions Garder / Oublier pour les faits temporaires)."""
    rep = rep or await run()
    s = settings()
    if s["summary"] and (rep["new_week"] or rep["merged"] or rep["contradictions"] or rep["stale"] or rep["expired"]
                         or rep["to_review"]):
        await notify.send("🧠 Ce qu'Atom a retenu cette semaine", summary_text(rep), tags="brain")
    for f in rep["to_review"][:5]:
        await notify.send("🧠 Toujours vrai ?", f"« {f['content']} »", tags="question",
                          buttons=[[("👍 Garder", f"mem:keep:{f['id']}"), ("🗑 Oublier", f"mem:forget:{f['id']}")]])
    return rep


def act(mid: int, action: str) -> dict:
    """Garder (le fait devient durable) ou oublier (archivé, restaurable)."""
    f = next((x for x in db.list_memories() if x["id"] == mid), None)
    if not f:
        return {"ok": False, "message": "Souvenir introuvable ou déjà archivé."}
    if action == "keep":
        db.set_memory_fields(mid, review_at=None, confidence=1.0)
        return {"ok": True, "message": f"👍 Gardé : « {f['content']} »"}
    if action == "forget":
        db.archive_memory(mid)
        return {"ok": True, "message": f"🗑 Oublié : « {f['content']} » (restaurable dans les réglages)"}
    return {"ok": False, "message": "Action inconnue."}


def due(s: dict, now, last_date: str | None) -> bool:
    if not s["enabled"] or now.weekday() != s["weekday"] or last_date == now.strftime("%Y-%m-%d"):
        return False
    h, m = (int(x) for x in s["time"].split(":"))
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    return 0 <= (now - target).total_seconds() < 6 * 3600


async def scheduler() -> None:
    from .reminders import now_local
    while True:
        try:
            n = now_local()
            if due(settings(), n, db.kv_get("memory_care_date")):
                db.kv_set("memory_care_date", n.strftime("%Y-%m-%d"))
                await weekly()
        except Exception:
            log.exception("entretien de la mémoire")
        await asyncio.sleep(60)
