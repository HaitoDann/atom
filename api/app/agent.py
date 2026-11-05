"""Cœur de l'agent : prompt, boucle de chat en streaming, commandes, mémoire.

Utilisé par l'interface web (NDJSON) et par Telegram.
"""

from __future__ import annotations

import asyncio
import re
from typing import AsyncIterator

import httpx

from . import companion, db, llm, memory, reminders, search
from .config import ATTACH_MAX_CHARS, CONTEXT_TURNS, EMOTIONS, OLLAMA_URL

TAG_RE = re.compile(r"^\s*\[([a-zA-Z]+)\]\s*")
_background: set[asyncio.Task] = set()


def system_prompt(persona: str, memory_block: str, web: str = "off", web_block: str = "") -> str:
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
        "fear = inquiet, thinking = perplexe, sleep = fatigué, idle = calme, "
        "curious = intrigué, focus = concentré sur une tâche)\n"
        "Exemple : [joy] Ravi de te revoir !\n"
        "Ne réfléchis pas à voix haute, ne décris pas ton raisonnement : réponds directement.\n"
        "/no_think\n\n"
        + reminders.prompt_block()
    )
    if web == "auto":
        s += (
            "\n\nTu peux chercher sur Internet. Si la question porte sur l'actualité, un prix, la météo, "
            "un horaire, un résultat, une version récente ou un fait précis que tu ne connais pas avec "
            "certitude, réponds UNIQUEMENT par la commande suivante, sans autre texte :\n"
            "[[recherche mots-clés précis]]\n"
            "Ne cherche pas pour bavarder, ni pour ce que tu sais déjà ou ce qui concerne l'utilisateur."
        )
    if memory_block:
        s += "\n\n" + memory_block
    if web_block:
        s += "\n\n" + web_block
    return s


def make_title(text: str) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    return t if len(t) <= 48 else t[:46].rstrip() + "…"


def with_attachments(text: str, attachments: list[dict] | None) -> str:
    """Contenu envoyé au modèle : le message, précédé des fichiers joints."""
    if not attachments:
        return text
    parts = []
    for a in attachments:
        body = (a.get("text") or "")[:ATTACH_MAX_CHARS]
        cut = " (tronqué)" if len(a.get("text") or "") > ATTACH_MAX_CHARS else ""
        parts.append(f"[Fichier joint : {a.get('name', 'fichier')}{cut}]\n```\n{body}\n```")
    return "\n\n".join(parts) + "\n\n" + (text or "Que peux-tu me dire de ce fichier ?")


async def chat_events(
    message: str,
    conversation_id: int | None,
    model: str,
    persona: str,
    auto_memory: bool,
    title_prefix: str = "",
    attachments: list[dict] | None = None,
    web: str = "auto",  # "auto" : Atom décide · "force" : chercher · "off" : jamais
) -> AsyncIterator[dict]:
    """Événements : meta, context, emotion, token…, reminder…, done, memory — ou error."""
    title_src = message or (attachments[0]["name"] if attachments else "Fichier")
    if conversation_id is None or not db.conversation_exists(conversation_id):
        conversation_id = db.create_conversation(title_prefix + make_title(title_src))
    elif not db.messages(conversation_id, 1):
        db.rename_conversation(conversation_id, title_prefix + make_title(title_src))
    db.set_conversation_model(conversation_id, model)
    yield dict(type="meta", conversation_id=conversation_id)

    history = db.messages(conversation_id, CONTEXT_TURNS * 2)
    mem_block, used = await memory.context_for(message or title_src, conversation_id)
    if used["facts"] or used["recall"]:
        yield dict(type="context", used=used)
    if not search.enabled():
        web = "off"
    msgs = [{"role": "system", "content": system_prompt(persona, mem_block, web if web == "auto" else "off")}]
    msgs += [
        {"role": m["role"], "content": with_attachments(m["content"], m["meta"].get("attachments"))}
        for m in history
    ]
    msgs.append({"role": "user", "content": with_attachments(message, attachments)})
    user_meta = {"attachments": attachments} if attachments else None
    user_id = db.add_message(conversation_id, "user", message, meta=user_meta)
    yield dict(type="ids", user_id=user_id)
    asst_meta = {"used": used} if (used["facts"] or used["recall"]) else None

    emotion: str | None = None
    saved = False
    text = ""
    sources: list[dict] = []
    if attachments:
        companion.bump("fed")

    async def run_pass(messages: list[dict], state: dict):
        """Un passage du modèle : émotion, jetons, commandes (dans state)."""
        cmds = reminders.CommandFilter()
        head, emo, out = "", None, ""
        async for tok in llm.stream_chat(model, messages):
            if emo is None:
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
                    emo = m.group(1).lower()
                    tok = stripped[m.end():]
                else:
                    emo = "talking"
                    tok = stripped
                yield dict(type="emotion", emotion=emo)
            tok = cmds.feed(tok)
            if tok:
                out += tok
                state["text"] = out
                yield dict(type="token", text=tok)
        if emo is None:  # réponse vide ou tag seul
            emo = "talking"
            rest = "" if head.lstrip().startswith("<think>") else TAG_RE.sub("", head).strip()
            out += cmds.feed(rest)
        rest = cmds.flush()
        if rest:
            out += rest
            yield dict(type="token", text=rest)
        state.update(text=out, emotion=emo, commands=cmds.commands)

    async def do_search(query: str):
        yield dict(type="search", status="start", query=query)
        try:
            results = await search.search(query)
        except Exception as e:  # noqa: BLE001
            yield dict(type="search", status="error", query=query, message=str(e))
            return
        companion.bump("fed")
        sources.extend({"title": r["title"], "url": r["url"], "domain": r["domain"]} for r in results)
        yield dict(type="search", status="done", query=query, sources=sources)
        today = reminders.now_local().strftime("%d/%m/%Y")
        msgs[0]["content"] = system_prompt(persona, mem_block, "off", search.prompt_block(query, results, today))

    try:
        state: dict = {}
        if web == "force" and search.enabled():
            async for ev in do_search((message or title_src)[:200]):
                yield ev
            if sources:
                async for ev in run_pass(msgs, state):
                    yield ev
        if not state:
            async for ev in run_pass(msgs, state):
                yield ev
            asked = [arg for cmd, arg in state["commands"] if cmd.lower() == "recherche"]
            if asked and search.enabled() and web != "off":
                if state["text"].strip():
                    yield dict(type="reset")
                async for ev in do_search(asked[0].strip()[:200]):
                    yield ev
                state = {}
                async for ev in run_pass(msgs, state):
                    yield ev
        text, emotion = state.get("text", ""), state.get("emotion", "talking")
        for cmd, arg in state.get("commands", []):
            if cmd.lower() != "recherche":
                yield reminders.execute(cmd, arg, conversation_id)
        text = text.strip() or "…"
        if sources:
            asst_meta = {**(asst_meta or {}), "sources": sources}
        asst_id = db.add_message(conversation_id, "assistant", text, emotion, meta=asst_meta)
        saved = True
        yield dict(type="done", emotion=emotion, id=asst_id)
    except GeneratorExit:
        # Arrêt demandé par l'utilisateur (bouton Stop) : on garde le début de réponse.
        partial = (locals().get("state") or {}).get("text", "")
        if not saved and partial.strip():
            db.add_message(conversation_id, "assistant", partial.strip() + " …", emotion or "talking", meta=asst_meta)
        raise
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
