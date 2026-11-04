"""Cœur de l'agent : prompt, boucle de chat en streaming, commandes, mémoire.

Utilisé par l'interface web (NDJSON) et par Telegram.
"""

from __future__ import annotations

import asyncio
import re
from typing import AsyncIterator

import httpx

from . import db, llm, memory, reminders
from .config import CONTEXT_TURNS, EMOTIONS, OLLAMA_URL

TAG_RE = re.compile(r"^\s*\[([a-zA-Z]+)\]\s*")
_background: set[asyncio.Task] = set()


def system_prompt(persona: str, memory_block: str) -> str:
    s = (
        f"{persona.strip()}\n\n"
        "Tu possèdes un corps : une sphère de fragments lumineux qui exprime ton état.\n\n"
        "Longueur des réponses — adapte-toi à la demande :\n"
        "- Conversation, salutation, question simple : une à trois phrases, naturellement.\n"
        "- Demande de travail (explication, comparaison, tableau, liste, code, rédaction) : "
        "réponse complète et structurée en Markdown (titres courts, listes, tableaux, blocs de code).\n\n"
        "Commence TOUJOURS ta réponse par ton émotion entre crochets, puis ton message. "
        f"Émotions possibles : {', '.join(EMOTIONS)}.\n"
        "(talking = neutre, joy = content, sad = triste, angry = agacé, surprise = étonné, "
        "fear = inquiet, thinking = perplexe, sleep = fatigué, idle = calme)\n"
        "Exemple : [joy] Ravi de te revoir !\n"
        "Ne réfléchis pas à voix haute, ne décris pas ton raisonnement : réponds directement.\n"
        "/no_think\n\n"
        + reminders.prompt_block()
    )
    if memory_block:
        s += "\n\n" + memory_block
    return s


def make_title(text: str) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    return t if len(t) <= 48 else t[:46].rstrip() + "…"


async def chat_events(
    message: str,
    conversation_id: int | None,
    model: str,
    persona: str,
    auto_memory: bool,
    title_prefix: str = "",
) -> AsyncIterator[dict]:
    """Événements : meta, emotion, token…, reminder…, done, memory — ou error."""
    if conversation_id is None or not db.conversation_exists(conversation_id):
        conversation_id = db.create_conversation(title_prefix + make_title(message))
    elif not db.messages(conversation_id, 1):
        db.rename_conversation(conversation_id, title_prefix + make_title(message))
    yield dict(type="meta", conversation_id=conversation_id)

    history = db.messages(conversation_id, CONTEXT_TURNS * 2)
    mem_block = await memory.context_for(message, conversation_id)
    msgs = [{"role": "system", "content": system_prompt(persona, mem_block)}]
    msgs += [{"role": m["role"], "content": m["content"]} for m in history]
    msgs.append({"role": "user", "content": message})
    db.add_message(conversation_id, "user", message)

    emotion: str | None = None
    cmds = reminders.CommandFilter()
    head = ""  # tampon tant que le tag d'émotion n'est pas résolu
    text = ""
    try:
        async for tok in llm.stream_chat(model, msgs):
            if emotion is None:
                head += tok
                # Raisonnement interne (modèles "thinking") : on l'écarte.
                if "</think>" in head:
                    head = head.split("</think>")[-1]
                elif head.lstrip().startswith("<think>") or "<think>".startswith(head.lstrip()[:7] or "x"):
                    continue
                stripped = head.lstrip()
                if not stripped:
                    continue
                if stripped.startswith("[") and "]" not in stripped and len(stripped) < 20:
                    continue  # le tag arrive encore
                m = TAG_RE.match(stripped)
                if m and m.group(1).lower() in EMOTIONS:
                    emotion = m.group(1).lower()
                    tok = stripped[m.end():]
                else:
                    emotion = "talking"
                    tok = stripped
                yield dict(type="emotion", emotion=emotion)
            tok = cmds.feed(tok)
            if tok:
                text += tok
                yield dict(type="token", text=tok)
        if emotion is None:  # réponse vide ou tag seul
            emotion = "talking"
            rest = "" if head.lstrip().startswith("<think>") else TAG_RE.sub("", head).strip()
            cmds.feed(rest)
        rest = cmds.flush()
        if rest:
            text += rest
            yield dict(type="token", text=rest)
        for cmd, arg in cmds.commands:
            yield reminders.execute(cmd, arg, conversation_id)
        text = text.strip() or "…"
        db.add_message(conversation_id, "assistant", text, emotion)
        yield dict(type="done", emotion=emotion)
    except Exception as e:  # noqa: BLE001 — on renvoie l'erreur à l'interface
        msg = str(e) or e.__class__.__name__
        if isinstance(e, httpx.ConnectError):
            msg = f"Impossible de joindre Ollama sur {OLLAMA_URL}."
        yield dict(type="error", message=msg)
        return

    if not auto_memory:
        return
    # Mémorisation en tâche de fond : elle survit même si le navigateur se ferme.
    task = asyncio.create_task(memory.after_exchange(model, conversation_id, message, text))
    _background.add(task)
    task.add_done_callback(_background.discard)
    try:
        added = await asyncio.wait_for(asyncio.shield(task), timeout=120)
        if added:
            yield dict(type="memory", added=added)
    except asyncio.TimeoutError:
        pass
