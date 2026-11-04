"""Mémoire automatique.

- Après chaque échange, le modèle extrait les faits durables sur l'utilisateur
  (en arrière-plan : la réponse n'est pas ralentie).
- L'échange est indexé pour pouvoir être rappelé dans une autre conversation.
- À chaque message, les faits et échanges passés les plus proches sont injectés
  dans le prompt système.
"""

from __future__ import annotations

import logging

import numpy as np

from . import db, llm
from .config import (
    DUPLICATE_SCORE,
    FACT_MIN_SCORE,
    FACTS_IN_PROMPT,
    RECALL_IN_PROMPT,
    RECALL_MIN_SCORE,
)

log = logging.getLogger("atom.memory")

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {"faits": {"type": "array", "items": {"type": "string"}, "maxItems": 3}},
    "required": ["faits"],
}

EXTRACT_PROMPT = """Tu es le module de mémoire d'un assistant personnel.
Lis l'échange ci-dessous et extrais UNIQUEMENT les informations durables sur l'utilisateur,
utiles dans de futures conversations : identité, prénom, métier, lieu, entourage, matériel,
projets en cours, goûts, préférences, habitudes, objectifs.

Règles :
- Ignore les questions générales, les demandes ponctuelles, et tout ce que dit l'assistant.
- Une phrase courte et autonome par fait, à la 3e personne : « L'utilisateur … ».
- N'invente rien. Ne répète pas un fait déjà connu.
- S'il n'y a rien de durable, renvoie une liste vide (c'est le cas le plus fréquent).

Faits déjà connus :
{known}

Échange :
Utilisateur : {user}
Assistant : {assistant}"""


def _top(query: np.ndarray, items: list[dict], k: int, min_score: float) -> list[tuple[float, dict]]:
    scored = [
        (float(np.dot(query, it["embedding"])), it)
        for it in items
        if it["embedding"] is not None and it["embedding"].shape == query.shape
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for s in scored[:k] if s[0] >= min_score]


async def context_for(message: str, conversation_id: int) -> str:
    """Bloc de mémoire à ajouter au prompt système pour ce message."""
    facts = db.list_memories()
    recall = db.list_recall()
    if not facts and not recall:
        return ""

    q = await llm.embed([message], kind="query")
    parts: list[str] = []
    if q is None:
        # Pas d'embeddings : on donne les faits les plus récents.
        chosen = [f["content"] for f in facts[-FACTS_IN_PROMPT * 2:]]
        if chosen:
            parts.append("Ce que tu sais de l'utilisateur :\n" + "\n".join(f"- {c}" for c in chosen))
        return "\n\n".join(parts)

    qv = q[0]
    await _backfill(facts)
    # Faits : les plus pertinents, complétés par les plus récents s'il en reste peu.
    best = [f for _, f in _top(qv, facts, FACTS_IN_PROMPT, FACT_MIN_SCORE)]
    for f in reversed(facts):
        if len(best) >= min(FACTS_IN_PROMPT, 4):
            break
        if f not in best:
            best.append(f)
    if best:
        parts.append(
            "Ce que tu sais de l'utilisateur (utilise-le naturellement, sans le réciter) :\n"
            + "\n".join(f"- {f['content']}" for f in best)
        )

    others = [r for r in recall if r["conversation_id"] != conversation_id]
    hits = _top(qv, others, RECALL_IN_PROMPT, RECALL_MIN_SCORE)
    if hits:
        parts.append(
            "Extraits d'anciennes conversations qui pourraient être utiles :\n"
            + "\n".join(f"- {h['text'][:500]}" for _, h in hits)
        )
    return "\n\n".join(parts)


async def _backfill(facts: list[dict]) -> None:
    """Calcule les embeddings manquants (souvenirs manuels, migration v1)."""
    missing = [f for f in facts if f["embedding"] is None]
    if not missing:
        return
    vecs = await llm.embed([f["content"] for f in missing])
    if vecs is None:
        return
    for f, v in zip(missing, vecs):
        db.set_memory_embedding(f["id"], v)
        f["embedding"] = v


async def remember(text: str, source: str = "manuel") -> dict | None:
    """Ajoute un fait, sauf s'il duplique un fait existant."""
    text = text.strip()
    if not text:
        return None
    facts = db.list_memories()
    if any(f["content"].lower() == text.lower() for f in facts):
        return None
    vec = await llm.embed([text])
    v = vec[0] if vec else None
    if v is not None:
        await _backfill(facts)
        if _top(v, facts, 1, DUPLICATE_SCORE):
            return None
    mid = db.add_memory(text, source, v)
    return {"id": mid, "content": text, "source": source}


async def after_exchange(model: str, conversation_id: int, user: str, assistant: str) -> list[dict]:
    """Indexe l'échange et en extrait les nouveaux faits. Renvoie les faits ajoutés."""
    added: list[dict] = []
    try:
        vec = await llm.embed([f"Utilisateur : {user}\nAtom : {assistant}"])
        if vec:
            db.add_recall(conversation_id, f"Utilisateur : {user[:400]} — Atom : {assistant[:400]}", vec[0])

        known = db.list_memories()
        known_txt = "\n".join(f"- {f['content']}" for f in known[-40:]) or "(aucun)"
        prompt = EXTRACT_PROMPT.format(known=known_txt, user=user[:2000], assistant=assistant[:1500])
        out = await llm.json_chat(model, [{"role": "user", "content": prompt}], EXTRACT_SCHEMA)
        for fact in (out.get("faits") or [])[:3]:
            if isinstance(fact, str) and 8 <= len(fact.strip()) <= 300:
                m = await remember(fact, source="auto")
                if m:
                    added.append(m)
    except Exception:  # noqa: BLE001 — la mémoire ne doit jamais casser le chat
        log.exception("échec de la mémorisation")
    return added
