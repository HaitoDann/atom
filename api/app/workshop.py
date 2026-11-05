"""Atelier multi-IA : plusieurs modèles travaillent ensemble sur une demande importante.

Schémas :
- « review »  : un rédacteur écrit, un relecteur critique, le rédacteur corrige.
- « panel »   : plusieurs participants proposent chacun une réponse, un arbitre fait la synthèse.
- « debate »  : deux participants défendent des positions opposées, un arbitre tranche.

Participants : « local » (Ollama) ou « remote:<modèle> » (fournisseur du mode hybride).
Confidentialité : l'atelier ne reçoit que ta demande et le fil récent de la conversation —
ni souvenirs, ni bibliothèque, ni fichiers.
"""

from __future__ import annotations

import json
import re
from typing import AsyncIterator

from . import db, hybrid, llm
from .config import DEFAULT_MODEL

DEFAULTS = {
    "enabled": False,
    "pattern": "review",
    "participants": ["local", "local", "local"],   # rôles selon le schéma (voir ROLES)
    "rounds": 1,                                   # tours de relecture (review)
}

ROLES = {
    "review": ["Rédacteur", "Relecteur", "Correction"],
    "panel": ["Proposition A", "Proposition B", "Arbitre"],
    "debate": ["Pour", "Contre", "Arbitre"],
}
PATTERNS = {
    "review": "Rédaction puis relecture",
    "panel": "Comité et arbitre",
    "debate": "Débat contradictoire",
}

TAG_RE = re.compile(r"^\s*\[[a-zA-Z]+\]\s*")
THINK_RE = re.compile(r"<think>[\s\S]*?</think>")


def settings() -> dict:
    s = dict(DEFAULTS)
    raw = db.kv_get("workshop")
    if raw:
        try:
            s.update({k: v for k, v in json.loads(raw).items() if k in DEFAULTS})
        except ValueError:
            pass
    return s


def save_settings(new: dict) -> dict:
    s = settings()
    s.update({k: v for k, v in new.items() if k in DEFAULTS})
    if s["pattern"] not in ROLES:
        s["pattern"] = "review"
    s["participants"] = [p for p in s["participants"] if isinstance(p, str)][:3] or ["local"] * 3
    while len(s["participants"]) < 3:
        s["participants"].append(s["participants"][-1])
    s["rounds"] = max(1, min(3, int(s.get("rounds", 1))))
    db.kv_set("workshop", json.dumps(s))
    return s


def engine_label(engine: str) -> str:
    if engine == "local":
        return f"Local · {(db.kv_get('model') or DEFAULT_MODEL).split(':')[0]}"
    return f"{hybrid.REMOTE_NAME} · {engine.split(':', 1)[1] or hybrid.model()}"


def _resolve(engine: str) -> str:
    """Un participant distant devient local si le fournisseur est absent ou le quota épuisé."""
    if engine.startswith("remote") and (not hybrid.configured() or hybrid.quota_left() <= 0):
        return "local"
    return engine


async def _gen(engine: str, messages: list[dict]) -> AsyncIterator[str]:
    if engine.startswith("remote"):
        name = engine.split(":", 1)[1] if ":" in engine else ""
        async for t in hybrid.stream(messages, name or None):
            yield t
    else:
        async for t in llm.stream_chat(db.kv_get("model") or DEFAULT_MODEL, messages):
            yield t


BASE = ("Tu participes à un atelier où plusieurs IA collaborent pour aider l'utilisateur. "
        "Réponds en français, directement, sans commencer par une émotion entre crochets, "
        "sans réfléchir à voix haute. /no_think")


def _prompts(pattern: str, step: int, request: str, prev: list[str]) -> list[dict]:
    """Messages pour l'étape `step` du schéma, à partir des sorties précédentes."""
    if pattern == "review":
        if step == 0:
            sys = BASE + " Ton rôle : RÉDACTEUR. Produis la meilleure réponse complète possible."
            user = request
        elif step % 2 == 1:
            sys = BASE + (" Ton rôle : RELECTEUR exigeant. Liste précisément les erreurs, oublis, imprécisions "
                          "et améliorations possibles de la réponse ci-dessous. Ne réécris pas la réponse.")
            user = f"Demande :\n{request}\n\nRéponse à relire :\n{prev[-1]}"
        else:
            sys = BASE + (" Ton rôle : RÉDACTEUR. Réécris ta réponse en tenant compte de la relecture. "
                          "Donne uniquement la version finale, sans parler de la relecture.")
            user = f"Demande :\n{request}\n\nTa première version :\n{prev[-2]}\n\nRelecture :\n{prev[-1]}"
    elif pattern == "panel":
        if step < 2:
            sys = BASE + " Propose ta meilleure réponse, de façon indépendante."
            user = request
        else:
            sys = BASE + (" Ton rôle : ARBITRE. Compare les propositions, garde ce qui est juste et utile dans "
                          "chacune, corrige ce qui est faux, et rédige la réponse finale. Donne uniquement la réponse finale.")
            user = f"Demande :\n{request}\n\nProposition A :\n{prev[0]}\n\nProposition B :\n{prev[1]}"
    else:  # debate
        if step == 0:
            sys = BASE + " Ton rôle : défendre la réponse « oui » / l'option la plus favorable. Argumente solidement, sans caricaturer."
            user = request
        elif step == 1:
            sys = BASE + " Ton rôle : défendre la position opposée à celle-ci, avec des arguments solides."
            user = f"Question :\n{request}\n\nPosition à contredire :\n{prev[0]}"
        else:
            sys = BASE + (" Ton rôle : ARBITRE impartial. Pèse les arguments des deux positions, tranche quand c'est "
                          "possible, et donne une recommandation claire et nuancée.")
            user = f"Question :\n{request}\n\nPosition 1 :\n{prev[0]}\n\nPosition 2 :\n{prev[1]}"
    return [{"role": "system", "content": sys}, {"role": "user", "content": user}]


def plan(pattern: str, participants: list[str], rounds: int) -> list[tuple[str, str]]:
    """[(rôle, moteur)] dans l'ordre d'exécution."""
    p = (participants + [participants[-1]] * 3)[:3]
    if pattern == "review":
        steps = [("Rédacteur", p[0])]
        for _ in range(rounds):
            steps += [("Relecteur", p[1]), ("Correction", p[2] if p[2] else p[0])]
        return steps
    return [(ROLES[pattern][0], p[0]), (ROLES[pattern][1], p[1]), (ROLES[pattern][2], p[2])]


async def run(message: str, conversation_id: int | None, pattern: str | None = None,
              participants: list[str] | None = None, title: str = "") -> AsyncIterator[dict]:
    """Événements : meta, step (start/token/done), token… (réponse finale), done — ou error."""
    from .agent import make_title

    s = settings()
    pattern = pattern if pattern in ROLES else s["pattern"]
    participants = participants or s["participants"]
    if conversation_id is None or not db.conversation_exists(conversation_id):
        conversation_id = db.create_conversation("Atelier · " + make_title(title or message))
    yield dict(type="meta", conversation_id=conversation_id)

    # Contexte : les derniers échanges, résumés dans la demande (pas de mémoire ni de documents).
    hist = db.messages(conversation_id, 6)
    context = "\n".join(f"{'Utilisateur' if m['role'] == 'user' else 'Atom'} : {m['content'][:600]}" for m in hist)
    request = (f"Contexte de la conversation :\n{context}\n\nDemande actuelle :\n{message}" if context else message)
    user_id = db.add_message(conversation_id, "user", message)
    yield dict(type="ids", user_id=user_id)

    steps = plan(pattern, participants, s["rounds"])
    outputs: list[str] = []
    record = []
    try:
        for i, (role, engine) in enumerate(steps):
            engine = _resolve(engine)
            final = i == len(steps) - 1
            yield dict(type="step", status="start", index=i, role=role, engine=engine_label(engine), final=final)
            text, sent = "", 0
            async for tok in _gen(engine, _prompts(pattern, i, request, outputs)):
                text += tok
                # On retient le début le temps d'écarter un éventuel tag d'émotion ou bloc de réflexion.
                if len(text) < 30 and "]" not in text[:25]:
                    continue
                clean = TAG_RE.sub("", THINK_RE.sub("", text))
                piece, sent = clean[sent:], len(clean)
                if piece:
                    yield dict(type="token", text=piece) if final else dict(type="step", status="token", index=i, text=piece)
            clean = TAG_RE.sub("", THINK_RE.sub("", text))
            if clean[sent:]:
                piece = clean[sent:]
                yield dict(type="token", text=piece) if final else dict(type="step", status="token", index=i, text=piece)
            text = TAG_RE.sub("", THINK_RE.sub("", text)).strip()
            outputs.append(text)
            record.append({"role": role, "engine": engine_label(engine), "text": text})
            yield dict(type="step", status="done", index=i, text=text)
        final_text = outputs[-1] if outputs else "…"
        meta = {"workshop": {"pattern": pattern, "name": PATTERNS[pattern], "steps": record[:-1]}}
        asst_id = db.add_message(conversation_id, "assistant", final_text, "focus", meta=meta)
        yield dict(type="done", emotion="focus", id=asst_id, final=final_text)
    except Exception as e:  # noqa: BLE001
        yield dict(type="error", message=f"Atelier interrompu : {e}")
