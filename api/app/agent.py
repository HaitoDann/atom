"""Cœur de l'agent : prompt, boucle de chat en streaming, commandes, mémoire.

Utilisé par l'interface web (NDJSON) et par Telegram.
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import AsyncIterator

import httpx

from .security import UNTRUSTED_RULE, untrusted
from . import db, hybrid, library, llm, memory, proxmox, reminders, search, spaces
from .config import ATTACH_MAX_CHARS, CONTEXT_TURNS, EMOTIONS, OLLAMA_URL
import logging

log = logging.getLogger("atom.agent")

TAG_RE = re.compile(r"^\s*\[([a-zA-Z]+)\]\s*")
_background: set[asyncio.Task] = set()


def system_prompt(persona: str, memory_block: str, web: str = "off", web_block: str = "", docs_block: str = "") -> str:
    s = (
        f"{persona.strip()}\n\n"
        "Tu possèdes un corps : une sphère de fragments lumineux qui exprime ton état.\n\n"
        "Longueur des réponses — adapte-toi à la demande :\n"
        "- Conversation, salutation, question simple : une à trois phrases, naturellement.\n"
        "- Demande de travail (explication, comparaison, tableau, liste, code, rédaction) : "
        "réponse complète et structurée en Markdown (titres courts, listes, tableaux, blocs de code).\n\n"
        "Commence TOUJOURS ta réponse par ton émotion entre crochets, puis ton message. "
        "Émotions possibles : talking (neutre, par défaut), joy (satisfait, content), curious (intrigué, intéressé), "
        "concerned (préoccupé, désolé, inquiet). Utilise surtout talking.\n"
        "Exemple : [joy] Ravi de te revoir !\n"
        "Pour un schéma (architecture, étapes d'un processus, plan d'un sujet, carte mentale, chronologie), "
        "dessine-le dans un bloc ```mermaid (flowchart, sequenceDiagram, mindmap ou timeline), avec des libellés courts.\n"
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
    if docs_block:
        s += "\n\n" + docs_block
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
        parts.append(f"[Fichier joint : {a.get('name', 'fichier')}{cut}]\n" + untrusted(body, "fichier joint"))
    return UNTRUSTED_RULE + "\n\n" + "\n\n".join(parts) + "\n\n" + (text or "Que peux-tu me dire de ce fichier ?")


async def chat_events(
    message: str,
    conversation_id: int | None,
    model: str,
    persona: str,
    auto_memory: bool,
    title_prefix: str = "",
    attachments: list[dict] | None = None,
    web: str = "auto",  # "auto" : Atom décide · "force" : chercher · "off" : jamais
    scope: str = "auto",  # bibliothèque : "auto" (documents), "none", ou "3,5" (collections choisies)
    engine: str = "default",  # "default" (réglage), "local", "mistral", "auto"
    space_id: int | None = None,
) -> AsyncIterator[dict]:
    """Événements : meta, context, emotion, token…, reminder…, done, memory — ou error."""
    title_src = message or (attachments[0]["name"] if attachments else "Fichier")
    if conversation_id is None or not db.conversation_exists(conversation_id):
        conversation_id = db.create_conversation(title_prefix + make_title(title_src))
        if space_id and spaces.get(space_id):
            spaces.assign(conversation_id, space_id)
    elif not db.messages(conversation_id, 1):
        db.rename_conversation(conversation_id, title_prefix + make_title(title_src))
    db.set_conversation_model(conversation_id, model)
    space = spaces.of_conversation(conversation_id)
    if space:
        persona = persona.strip() + "\n\n" + spaces.prompt_block(space)
    yield dict(type="meta", conversation_id=conversation_id, space_id=space["id"] if space else None)

    history = db.messages(conversation_id, CONTEXT_TURNS * 2)
    mem_block, used = await memory.context_for(message or title_src, conversation_id)
    if used["facts"] or used["recall"]:
        yield dict(type="context", used=used)
    if not search.enabled():
        web = "off"
    # Bibliothèque : passages de tes documents / ton code proches de la question
    docs_block, doc_refs = "", []
    if scope != "none":
        try:
            if scope == "auto" and space and space["collections"]:
                ids = list(space["collections"])   # dans un espace : ses collections d'abord
            elif scope == "auto":
                ids = [c["id"] for c in library.list_collections() if c["kind"] == "docs"]
            else:
                ids = [int(x) for x in scope.split(",") if x.strip().isdigit()]
            if ids:
                chosen = scope != "auto"
                hits = await library.retrieve(message or title_src, ids, k=6 if chosen else 4,
                                              min_score=0.35 if chosen else library.DOC_MIN_SCORE)
                if hits:
                    docs_block = library.prompt_block(hits)
                    doc_refs = [{"n": i + 1, "chunk_id": h["id"], "document_id": h["document_id"],
                                 "collection_id": h["collection_id"], "label": library.ref_label(h),
                                 "collection": h["collection"], "kind": h["kind"],
                                 "path": h.get("path") if h["kind"] == "code" else None,
                                 "line_start": h.get("line_start"), "page": h.get("page")} for i, h in enumerate(hits)]
                code_cols = [c for c in library.list_collections() if c["id"] in ids and c["kind"] == "code"] if chosen else []
                for c in code_cols[:2]:
                    docs_block += f"\n\nStructure du projet « {c['name']} » :\n{library.tree(c['id'], 60)}"
                if doc_refs or code_cols:
                    yield dict(type="docs", refs=doc_refs)
        except Exception:  # noqa: BLE001 — la bibliothèque ne doit pas bloquer la réponse
            import logging
            logging.getLogger("atom.agent").exception("recherche dans la bibliothèque impossible")
    # Question sur le serveur : l'état Proxmox relevé est ajouté (données privées, comme la bibliothèque)
    if proxmox.wants(message or ""):
        if time.time() - proxmox.state.get("updated", 0) > 90:
            await proxmox.poll()
        docs_block = (docs_block + "\n\n" if docs_block else "") + proxmox.prompt_block()
    msgs = [{"role": "system", "content": system_prompt(persona, mem_block, web if web == "auto" else "off", "", docs_block)}]
    msgs += [
        {"role": m["role"], "content": with_attachments(m["content"], m["meta"].get("attachments"))}
        for m in history
    ]
    msgs.append({"role": "user", "content": with_attachments(message, attachments)})
    # ---- quel moteur répond ?
    hs = hybrid.settings()
    provider, route_reason = hybrid.decide(engine, message, bool(mem_block), bool(docs_block) or bool(attachments))
    web_block_cur = ""

    def system_for(prov: str) -> str:
        """Prompt système selon le moteur : pour Mistral, seulement ce que tu as autorisé à sortir."""
        if prov == "local":
            return system_prompt(persona, mem_block, web if web == "auto" and not web_block_cur else "off",
                                 web_block_cur, docs_block)
        return system_prompt(persona, mem_block if hs["allow_memory"] else "",
                             web if web == "auto" and not web_block_cur else "off",
                             web_block_cur if hs["allow_web"] else "", docs_block if hs["allow_docs"] else "")

    msgs[0]["content"] = system_for(provider)
    if provider != "local" or route_reason:
        yield dict(type="route", provider=provider, model=hybrid.model() if provider != "local" else model,
                   reason=route_reason)
    user_meta = {"attachments": attachments} if attachments else None
    user_id = db.add_message(conversation_id, "user", message, meta=user_meta)
    yield dict(type="ids", user_id=user_id)
    asst_meta = {"used": used} if (used["facts"] or used["recall"]) else None

    emotion: str | None = None
    saved = False
    text = ""
    sources: list[dict] = []

    async def tokens_from(messages: list[dict]):
        """Jetons du moteur choisi ; si Mistral échoue avant d'écrire, on repasse en local."""
        nonlocal provider
        if provider == "mistral":
            got = False
            try:
                sensitive = bool((hs["allow_memory"] and mem_block) or (hs["allow_docs"] and (docs_block or attachments)))
                async for tok in hybrid.stream(messages, sensitive=sensitive):
                    got = True
                    yield tok
                return
            except Exception as e:  # noqa: BLE001
                log.warning("agent : erreur gérée", exc_info=True)
                if got:
                    raise
                log_reason = str(e) or e.__class__.__name__
                provider = "local"
                messages[0]["content"] = system_for("local")
                yield {"route": dict(type="route", provider="local", model=model,
                                     reason=f"Fournisseurs distants indisponibles ({log_reason}) : réponse en local.")}
        async for tok in llm.stream_chat(model, messages):
            yield tok

    async def run_pass(messages: list[dict], state: dict):
        """Un passage du modèle : émotion, jetons, commandes (dans state)."""
        cmds = reminders.CommandFilter()
        head, emo, out = "", None, ""
        async for tok in tokens_from(messages):
            if isinstance(tok, dict):
                yield tok["route"]
                continue
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
            log.warning("agent : erreur gérée", exc_info=True)
            yield dict(type="search", status="error", query=query, message=str(e))
            return
        sources.extend({"title": r["title"], "url": r["url"], "domain": r["domain"],
                        "snippet": (r.get("snippet") or r.get("content") or "")[:220]} for r in results)
        yield dict(type="search", status="done", query=query, sources=sources)
        today = reminders.now_local().strftime("%d/%m/%Y")
        nonlocal web_block_cur
        web_block_cur = search.prompt_block(query, results, today)
        msgs[0]["content"] = system_for(provider)

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
        rem_cards = []
        for cmd, arg in state.get("commands", []):
            if cmd.lower() != "recherche":
                ev = reminders.execute(cmd, arg, conversation_id)
                if ev.get("action") in ("created", "cancelled"):
                    rem_cards.append({k: ev.get(k) for k in ("action", "id", "text", "when", "due_at")})
                yield ev
        text = text.strip() or "…"
        if sources:
            asst_meta = {**(asst_meta or {}), "sources": sources}
        if doc_refs:
            asst_meta = {**(asst_meta or {}), "docs": doc_refs}
        if rem_cards:
            asst_meta = {**(asst_meta or {}), "reminders": rem_cards}
        if provider != "local":
            asst_meta = {**(asst_meta or {}), "provider": hybrid.last_used.get("name") or hybrid.name(),
                         "remote_model": hybrid.last_used.get("model") or hybrid.model()}
        asst_id = db.add_message(conversation_id, "assistant", text, emotion, meta=asst_meta)
        saved = True
        stats = dict(hybrid.last_stats if provider != "local" else llm.last_stats)
        yield dict(type="done", emotion=emotion, id=asst_id, stats=stats, provider=provider)
    except GeneratorExit:
        # Arrêt demandé par l'utilisateur (bouton Stop) : on garde le début de réponse.
        partial = (locals().get("state") or {}).get("text", "")
        if not saved and partial.strip():
            db.add_message(conversation_id, "assistant", partial.strip() + " …", emotion or "talking", meta=asst_meta)
        raise
    except Exception as e:  # noqa: BLE001 — on renvoie l'erreur à l'interface
        log.warning("agent : erreur gérée", exc_info=True)
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
