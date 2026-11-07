"""Mémoire automatique.

- Après chaque échange, le modèle extrait les faits durables sur l'utilisateur
  (en arrière-plan : la réponse n'est pas ralentie).
- L'échange est indexé pour pouvoir être rappelé dans une autre conversation.
- À chaque message, les faits et échanges passés les plus proches sont injectés
  dans le prompt système.
"""

from __future__ import annotations

import logging
import re
import time

import numpy as np

from . import db, llm
from .config import (
    PROVIDER,
    RECALL_SCAN,
    RELATED_SCORE,
    DUPLICATE_SCORE,
    FACT_MIN_SCORE,
    FACTS_IN_PROMPT,
    RECALL_IN_PROMPT,
    RECALL_MIN_SCORE,
)

log = logging.getLogger("atom.memory")

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {"faits": {"type": "array", "maxItems": 3, "items": {
        "type": "object",
        "properties": {
            "texte": {"type": "string"},
            "type": {"type": "string", "enum": ["semantique", "procedurale", "episodique"]},
            "importance": {"type": "integer", "minimum": 1, "maximum": 3},
            "duree": {"type": "string", "enum": ["durable", "temporaire"]},
        },
        "required": ["texte", "type", "importance", "duree"],
    }}},
    "required": ["faits"],
}

EXTRACT_PROMPT = """Tu es le module de mémoire d'un assistant personnel.
Lis l'échange ci-dessous et extrais UNIQUEMENT les informations durables sur l'utilisateur,
utiles dans de futures conversations.

Pour chaque fait :
- texte : une phrase courte et autonome, à la 3e personne (« L'utilisateur … ») ;
- type : « semantique » (qui il est, ce qu'il a, ce qu'il aime : métier, lieu, matériel, projets, goûts),
  « procedurale » (comment il travaille, ses habitudes et préférences de méthode : « préfère des réponses courtes »,
  « code en Go avec des tests »), « episodique » (un événement daté : « a déménagé en mars 2026 ») ;
- importance : 1 anecdotique, 2 utile, 3 essentiel (identité, contrainte forte) ;
- duree : « temporaire » si ce sera faux bientôt (« est malade cette semaine », « prépare un examen en juin »), sinon « durable ».

Règles : ignore les questions générales, les demandes ponctuelles et tout ce que dit l'assistant. N'invente rien.
Ne répète pas un fait déjà connu. S'il n'y a rien de durable, renvoie une liste vide (c'est le cas le plus fréquent).

Faits déjà connus :
{known}

Échange :
Utilisateur : {user}
Assistant : {assistant}"""

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "relation": {"type": "string", "enum": ["identique", "complement", "contradiction", "different"]},
        "fusion": {"type": "string"},
    },
    "required": ["relation", "fusion"],
}

JUDGE_PROMPT = """Deux informations sur l'utilisateur d'un assistant :
A (connue depuis le {date}) : {old}
B (nouvelle) : {new}

Quelle est la relation entre A et B ?
- identique : même information (formulée autrement) ;
- complement : B précise ou complète A sans la contredire → « fusion » = une seule phrase qui réunit les deux ;
- contradiction : B rend A fausse ou périmée (déménagement, changement de travail, de goût…) → « fusion » = B ;
- different : sujets différents → « fusion » = "".
Réponds en JSON."""

REVIEW_DAYS = 45   # un fait « temporaire » est retiré des réponses après ce délai, jusqu'à ce que tu le confirmes


def _top(query: np.ndarray, items: list[dict], k: int, min_score: float) -> list[tuple[float, dict]]:
    scored = [
        (float(np.dot(query, it["embedding"])), it)
        for it in items
        if it["embedding"] is not None and it["embedding"].shape == query.shape
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for s in scored[:k] if s[0] >= min_score]


async def context_for(message: str, conversation_id: int) -> tuple[str, dict]:
    """Bloc de mémoire pour le prompt système, et ce qui a été utilisé (affiché à l'utilisateur)."""
    used: dict = {"facts": [], "recall": []}
    now = time.time()
    facts = [f for f in db.list_memories() if not (f.get("review_at") and f["review_at"] < now)]   # temporaires périmés : écartés
    recall = db.list_recall(RECALL_SCAN, exclude_conversation=conversation_id)
    if not facts and not recall:
        return "", used

    q = await llm.embed([message], kind="query")
    parts: list[str] = []
    if q is None:
        # Pas d'embeddings : on donne les faits les plus récents.
        chosen = facts[-FACTS_IN_PROMPT * 2:]
        if chosen:
            parts.append("Ce que tu sais de l'utilisateur :\n" + "\n".join(f"- {c['content']}" for c in chosen))
            used["facts"] = [{"id": f["id"], "content": f["content"]} for f in chosen]
        return "\n\n".join(parts), used

    qv = q[0]
    await _backfill(facts)
    # Faits : score = pertinence, un peu d'importance et de confiance ; les habitudes (procédurales) passent en priorité.
    scored = []
    for f in facts:
        if f["embedding"] is None or f["embedding"].shape != qv.shape:
            continue
        sim = float(np.dot(qv, f["embedding"]))
        sc = sim + 0.04 * (f.get("importance") or 2) + 0.05 * (f.get("confidence") or 0.8)
        if sim >= FACT_MIN_SCORE or (f.get("kind") == "procedurale" and sim >= FACT_MIN_SCORE - 0.15) or (f.get("importance") or 2) >= 3:
            scored.append((sc, f))
    scored.sort(key=lambda x: x[0], reverse=True)
    best = [f for _, f in scored[:FACTS_IN_PROMPT]]
    for f in sorted(facts, key=lambda f: (-(f.get("importance") or 2), -(f.get("updated_at") or 0))):   # complément : essentiel puis récent
        if len(best) >= min(FACTS_IN_PROMPT, 4):
            break
        if f not in best:
            best.append(f)
    if best:
        proc = [f for f in best if f.get("kind") == "procedurale"]
        sem = [f for f in best if f.get("kind") != "procedurale"]
        if sem:
            parts.append("Ce que tu sais de l'utilisateur (utilise-le naturellement, sans le réciter) :\n"
                         + "\n".join(f"- {f['content']}" for f in sem))
        if proc:
            parts.append("Ses habitudes et préférences de travail (applique-les) :\n" + "\n".join(f"- {f['content']}" for f in proc))
        used["facts"] = [{"id": f["id"], "content": f["content"]} for f in best]
        db.touch_memories([f["id"] for f in best])

    # Épisodique : anciens échanges proches, avec une légère préférence pour les récents
    hits = []
    for r in recall:
        if r["embedding"] is None or r["embedding"].shape != qv.shape:
            continue
        sim = float(np.dot(qv, r["embedding"]))
        if sim >= RECALL_MIN_SCORE:
            age_days = (now - r["created_at"]) / 86400
            hits.append((sim - min(0.06, age_days / 3000), r))
    hits.sort(key=lambda x: x[0], reverse=True)
    hits = hits[:RECALL_IN_PROMPT]
    if hits:
        parts.append(
            "Extraits d'anciennes conversations qui pourraient être utiles :\n"
            + "\n".join(f"- {h['text'][:500]}" for _, h in hits)
        )
        used["recall"] = [{"conversation_id": h["conversation_id"], "text": h["text"][:300]} for _, h in hits]
    return "\n\n".join(parts), used


async def _backfill(facts: list[dict]) -> None:
    """Calcule les embeddings manquants (souvenirs manuels, migration v1)."""
    missing = [f for f in facts if f["embedding"] is None]
    if not missing:
        return
    vecs = await llm.embed([f["content"] for f in missing])
    if vecs is None:
        return
    for f, v in zip(missing, vecs, strict=False):
        db.set_memory_embedding(f["id"], v)
        f["embedding"] = v


async def remember(text: str, source: str = "manuel", kind: str = "semantique", importance: int = 2,
                   temporary: bool = False, model: str | None = None) -> dict | None:
    """Ajoute un fait après avoir vérifié doublons, compléments et contradictions.
    Renvoie {id, content, action} — action : added | merged | replaced — ou None si rien n'a changé."""
    text = text.strip()
    if not text:
        return None
    facts = db.list_memories()
    exact = next((f for f in facts if f["content"].lower() == text.lower()), None)
    if exact:
        db.set_memory_fields(exact["id"], confidence=min(1.0, (exact.get("confidence") or 0.8) + 0.1))
        return None
    vec = await llm.embed([text])
    v = vec[0] if vec else None
    review_at = time.time() + REVIEW_DAYS * 86400 if temporary else None
    conf = 1.0 if source == "manuel" else 0.75
    if v is not None:
        await _backfill(facts)
        near = _top(v, facts, 3, RELATED_SCORE)
        for score, old in near:
            if score >= DUPLICATE_SCORE:   # même chose : on renforce la confiance au lieu de dupliquer
                db.set_memory_fields(old["id"], confidence=min(1.0, (old.get("confidence") or 0.8) + 0.1),
                                     importance=max(old.get("importance") or 2, importance))
                return None
            rel = await _judge(old, text, model)
            if rel["relation"] == "identique":
                db.set_memory_fields(old["id"], confidence=min(1.0, (old.get("confidence") or 0.8) + 0.1))
                return None
            if rel["relation"] == "complement" and rel["fusion"].strip():
                merged = rel["fusion"].strip()[:300]
                mv = await llm.embed([merged])
                db.update_memory(old["id"], merged, mv[0] if mv else v)
                db.set_memory_fields(old["id"], importance=max(old.get("importance") or 2, importance))
                return {"id": old["id"], "content": merged, "source": source, "action": "merged"}
            if rel["relation"] == "contradiction":   # l'ancien fait est archivé (historique), le nouveau le remplace
                mid = db.add_memory(text, source, v, old.get("kind") or kind, max(old.get("importance") or 2, importance), conf, review_at)
                db.archive_memory(old["id"], superseded_by=mid)
                log.info("souvenir %s remplacé par %s (contradiction)", old["id"], mid)
                return {"id": mid, "content": text, "source": source, "action": "replaced", "replaced": old["content"]}
    mid = db.add_memory(text, source, v, kind, importance, conf, review_at)
    return {"id": mid, "content": text, "source": source, "action": "added"}


async def _judge(old: dict, new: str, model: str | None) -> dict:
    """Le modèle local tranche : même info, complément, contradiction ou sujet différent."""
    from .config import DEFAULT_MODEL
    if PROVIDER == "mock":
        o, n = old["content"].lower(), new.lower()
        if any(w in o and w in n for w in ("habite", "travaille")) and o != n:
            return {"relation": "contradiction", "fusion": new}
        return {"relation": "different", "fusion": ""}
    date = time.strftime("%d/%m/%Y", time.localtime(old.get("created_at") or time.time()))
    try:
        out = await llm.json_chat(model or db.kv_get("model") or DEFAULT_MODEL,
                                  [{"role": "user", "content": JUDGE_PROMPT.format(old=old["content"], new=new, date=date)}], JUDGE_SCHEMA)
    except Exception:  # noqa: BLE001
        log.warning("memory : erreur gérée", exc_info=True)
        out = {}
    if out.get("relation") not in ("identique", "complement", "contradiction", "different"):
        return {"relation": "different", "fusion": ""}
    return {"relation": out["relation"], "fusion": str(out.get("fusion") or "")}


def review_due() -> list[dict]:
    """Faits temporaires arrivés à échéance : à confirmer ou à oublier."""
    now = time.time()
    return [f for f in db.list_memories() if f.get("review_at") and f["review_at"] < now]


PERSONAL = re.compile(
    r"\b(je|j'|j’|moi|mon|ma|mes|m'appelle|suis|ai|aime|adore|déteste|préfère|habite|travaille|"
    r"femme|mari|copine|copain|enfant|fils|fille|chien|chat|projet|retiens|souviens|note)\b",
    re.I,
)


def worth_extracting(user: str) -> bool:
    """Évite de relancer le modèle pour « 2+2 » ou « merci » : il ne sert que si tu parles de toi."""
    u = user.strip()
    return len(u) >= 12 and bool(PERSONAL.search(u))


async def after_exchange(model: str, conversation_id: int, user: str, assistant: str) -> list[dict]:
    """Indexe l'échange et en extrait les nouveaux faits. Renvoie les faits ajoutés."""
    added: list[dict] = []
    try:
        vec = await llm.embed([f"Utilisateur : {user}\nAtom : {assistant}"])
        if vec:
            db.add_recall(conversation_id, f"Utilisateur : {user[:400]} — Atom : {assistant[:400]}", vec[0])

        if not worth_extracting(user):
            return added
        known = db.list_memories()
        known_txt = "\n".join(f"- {f['content']}" for f in known[-40:]) or "(aucun)"
        prompt = EXTRACT_PROMPT.format(known=known_txt, user=user[:2000], assistant=assistant[:1500])
        out = await llm.json_chat(model, [{"role": "user", "content": prompt}], EXTRACT_SCHEMA)
        for fact in (out.get("faits") or [])[:3]:
            if isinstance(fact, str):   # ancien format
                fact = {"texte": fact, "type": "semantique", "importance": 2, "duree": "durable"}
            if not isinstance(fact, dict):
                continue
            t = str(fact.get("texte") or "").strip()
            if 8 <= len(t) <= 300:
                kind = fact.get("type") if fact.get("type") in ("semantique", "procedurale", "episodique") else "semantique"
                imp = fact.get("importance") if fact.get("importance") in (1, 2, 3) else 2
                m = await remember(t, source="auto", kind=kind, importance=imp, temporary=fact.get("duree") == "temporaire", model=model)
                if m:
                    added.append(m)
    except Exception:  # noqa: BLE001 — la mémoire ne doit jamais casser le chat
        log.exception("échec de la mémorisation")
    return added
