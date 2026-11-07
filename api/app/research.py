"""Recherche approfondie (comme « Deep Research ») : plan → recherches → notes sourcées → complément → rapport.

- Le plan décompose la question en 3 à 6 recherches ciblées.
- Chaque lot de pages lues est résumé en notes factuelles, citées avec une numérotation globale [n].
- Une passe de vérification cherche ce qui manque ou se contredit (1 à 2 recherches de plus).
- Le rapport final est rédigé à partir des notes uniquement, avec les sources citées.
Seules la question et des contenus web publics sont envoyés aux API distantes (jamais tes souvenirs ni tes documents).
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import AsyncIterator

from . import db, hybrid, llm, search
from .config import DEFAULT_MODEL
import logging

log = logging.getLogger("atom.research")

MAX_QUERIES = 6


async def _ask(messages: list[dict], used: dict) -> str:
    """Moteur distant si disponible (plus capable), sinon local."""
    if hybrid.configured():
        try:
            out = "".join([t async for t in hybrid.stream(messages)])
            used["engine"] = hybrid.last_used.get("name") or "distant"
            return out
        except Exception:  # noqa: BLE001
            log.warning("research : erreur gérée", exc_info=True)
            pass
    used["engine"] = "local"
    return "".join([t async for t in llm.stream_chat(db.kv_get("model") or DEFAULT_MODEL, messages)])


async def _stream(messages: list[dict], used: dict) -> AsyncIterator[str]:
    if hybrid.configured():
        got = False
        try:
            async for t in hybrid.stream(messages):
                got = True
                yield t
            used["engine"] = hybrid.last_used.get("name") or "distant"
            return
        except Exception:  # noqa: BLE001
            log.warning("research : erreur gérée", exc_info=True)
            if got:
                raise
    used["engine"] = "local"
    async for t in llm.stream_chat(db.kv_get("model") or DEFAULT_MODEL, messages):
        yield t


def _json(text: str) -> dict:
    m = re.search(r"\{[\s\S]*\}", text)
    try:
        return json.loads(m.group(0)) if m else {}
    except ValueError:
        return {}


def _clean(text: str) -> str:
    return re.sub(r"^\s*\[[a-z_]+\]\s*", "", re.sub(r"<think>[\s\S]*?</think>", "", text)).strip()


SYS = "Tu es un assistant de recherche rigoureux. Réponds en français. Pas d'émotion entre crochets. /no_think"


async def run(question: str, conversation_id: int | None) -> AsyncIterator[dict]:
    from .agent import make_title

    if not search.enabled():
        yield dict(type="error", message="La recherche web n'est pas configurée (service SearXNG).")
        return
    if conversation_id is None or not db.conversation_exists(conversation_id):
        conversation_id = db.create_conversation("Recherche · " + make_title(question))
    yield dict(type="meta", conversation_id=conversation_id)
    user_id = db.add_message(conversation_id, "user", question, meta={"research": True})
    yield dict(type="ids", user_id=user_id)
    today = datetime.now().strftime("%d/%m/%Y")
    used: dict = {}

    # 1. Plan
    yield dict(type="progress", text="Élaboration du plan de recherche…")
    plan = _json(await _ask([{"role": "system", "content": SYS}, {"role": "user", "content":
        f"Question : {question}\nDate du jour : {today}\n\nDécompose cette question en 3 à {MAX_QUERIES} recherches web précises et "
        "complémentaires (mots-clés efficaces, en français ou en anglais selon le sujet), et propose le plan du rapport. "
        'Réponds uniquement en JSON : {"queries": ["…"], "outline": ["section 1", "…"]}'}], used))
    queries = [q for q in plan.get("queries", []) if isinstance(q, str) and q.strip()][:MAX_QUERIES] or [question]
    outline = [o for o in plan.get("outline", []) if isinstance(o, str)][:8]
    yield dict(type="progress", text="Plan : " + " · ".join(queries), queries=queries)

    sources: list[dict] = []
    seen: set[str] = set()
    notes: list[str] = []

    async def investigate(q: str) -> AsyncIterator[dict]:
        yield dict(type="progress", text=f"Recherche : {q}")
        try:
            results = await search.search(q)
        except Exception as e:  # noqa: BLE001
            log.warning("research : erreur gérée", exc_info=True)
            yield dict(type="progress", text=f"Recherche impossible ({e})")
            return
        fresh = []
        for r in results:
            if r["url"] in seen:
                continue
            seen.add(r["url"])
            sources.append({"title": r["title"], "url": r["url"], "domain": r["domain"],
                            "snippet": (r.get("snippet") or r.get("content") or "")[:220]})
            fresh.append((len(sources), r))
        readable = [(n, r) for n, r in fresh if r.get("content") or r.get("snippet")][:4]
        if not readable:
            return
        yield dict(type="sources", sources=sources)
        yield dict(type="progress", text=f"Lecture de {len(readable)} page(s) : " + ", ".join(r["domain"] for _, r in readable))
        from .security import UNTRUSTED_RULE, untrusted
        block = UNTRUSTED_RULE + "\n\n" + "\n\n".join(f"[{n}] " + untrusted(f"{r['title']} — {r['domain']}\n{(r.get('content') or r.get('snippet'))[:2200]}", f"page web {r['domain']}") for n, r in readable)
        note = _clean(await _ask([{"role": "system", "content": SYS}, {"role": "user", "content":
            f"Question générale : {question}\nRecherche en cours : {q}\n\nSources :\n{block}\n\n"
            "Extrais les faits utiles à la question, sous forme de puces courtes. Chaque puce se termine par le numéro de "
            "sa source entre crochets, ex. [3]. Note les chiffres, dates et désaccords entre sources. N'invente rien : "
            "si les sources ne disent rien d'utile, réponds « (rien d'utile) »."}], used))
        if note and "rien d'utile" not in note.lower()[:40]:
            notes.append(f"### {q}\n{note}")

    # 2. Recherches
    for q in queries:
        async for ev in investigate(q):
            yield ev

    # 3. Complément : ce qui manque ou se contredit
    if notes:
        yield dict(type="progress", text="Vérification : ce qui manque ou se contredit…")
        gap = _json(await _ask([{"role": "system", "content": SYS}, {"role": "user", "content":
            f"Question : {question}\n\nNotes :\n" + "\n\n".join(notes)[:9000] +
            "\n\nQuelles informations importantes manquent, ou quels points se contredisent et méritent une vérification ? "
            'Propose 0 à 2 recherches. Réponds uniquement en JSON : {"queries": ["…"]}'}], used))
        for q in [x for x in gap.get("queries", []) if isinstance(x, str) and x.strip()][:2]:
            async for ev in investigate(q):
                yield ev

    if not notes:
        msg = "Je n'ai trouvé aucune source exploitable pour cette question. Essaie de la reformuler ou de la préciser."
        asst = db.add_message(conversation_id, "assistant", msg, "sad", meta={"sources": sources} if sources else None)
        yield dict(type="token", text=msg)
        yield dict(type="done", id=asst)
        return

    # 4. Rapport
    yield dict(type="progress", text=f"Rédaction du rapport à partir de {len(sources)} sources…")
    plan_txt = ("Plan suggéré : " + " ; ".join(outline) + "\n") if outline else ""
    msgs = [{"role": "system", "content": SYS}, {"role": "user", "content":
        f"Question : {question}\nDate : {today}\n{plan_txt}\nNotes de recherche (avec numéros de sources) :\n" + "\n\n".join(notes)[:14000] +
        "\n\nRédige un rapport en Markdown, à partir de ces notes uniquement :\n"
        "- commence par **En bref** (3 à 5 phrases qui répondent directement) ;\n"
        "- puis des sections avec titres ##, tableaux si utile ;\n"
        "- cite les sources avec leur numéro [n] après chaque fait ;\n"
        "- termine par **Points d'attention** : désaccords entre sources, informations datées ou incertaines.\n"
        "N'ajoute aucune information absente des notes."}]
    text = ""
    async for tok in _stream(msgs, used):
        text += tok
        yield dict(type="token", text=tok)
    text = _clean(text) or "…"
    meta = {"sources": sources, "research": {"queries": queries, "engine": used.get("engine")}}
    asst = db.add_message(conversation_id, "assistant", text, "focus", meta=meta)
    yield dict(type="done", id=asst)
