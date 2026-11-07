"""Bot Telegram : discuter avec Atom depuis n'importe où.

- Long polling (getUpdates) : c'est Atom qui va chercher les messages chez
  Telegram, aucun port à ouvrir, fonctionne hors du réseau local.
- Seuls les identifiants listés dans ATOM_TELEGRAM_ALLOWED sont servis.
- Chaque discussion Telegram a sa propre conversation Atom (/nouveau pour en changer).
- La réponse s'affiche progressivement (édition du message), puis est mise en forme.
- L'émotion d'Atom apparaît en réaction sur ton message.
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
import time

import httpx

from . import agent, db
from .config import DEFAULT_MODEL, DEFAULT_PERSONA, TELEGRAM_ALLOWED, TELEGRAM_TOKEN

log = logging.getLogger("atom.telegram")
API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
EDIT_EVERY = 1.5  # secondes entre deux mises à jour du message en cours
LIMIT = 4000      # Telegram : 4096 caractères max par message

REACTIONS = {
    "joy": "😁", "sad": "😢", "angry": "😡", "surprise": "🤯",
    "fear": "😨", "thinking": "🤔", "sleep": "😴", "concerned": "😕", "curious": "🧐",
}

HELP = (
    "Salut, c'est Atom ✨\n\n"
    "Écris-moi normalement, je te réponds ici.\n\n"
    "/nouveau — commencer une nouvelle conversation\n"
    "/rappels — voir les rappels programmés\n"
    "/souvenirs — ce que je sais de toi\n"
    "/serveur — état du serveur Proxmox\n"
    "/agent projet tâche — confier une tâche à l'agent de code\n"
    "/aide — ce message"
)


def enabled() -> bool:
    return bool(TELEGRAM_TOKEN)


# ---------------------------------------------------------------- API bas niveau


class TelegramError(RuntimeError):
    pass


async def call(client: httpx.AsyncClient, method: str, **params) -> dict:
    r = await client.post(f"{API}/{method}", json=params)
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if not data.get("ok"):
        raise TelegramError(f"{method}: {data.get('description') or r.status_code}")
    return data.get("result")


async def send_text(client, chat_id: int, text: str, **extra) -> dict | None:
    """Envoie en HTML mis en forme, et retombe en texte brut si Telegram refuse."""
    try:
        return await call(client, "sendMessage", chat_id=chat_id, text=to_html(text),
                          parse_mode="HTML", disable_web_page_preview=True, **extra)
    except TelegramError:
        return await call(client, "sendMessage", chat_id=chat_id, text=text[:LIMIT], **extra)


async def edit_text(client, chat_id: int, message_id: int, text: str, formatted: bool) -> None:
    try:
        if formatted:
            await call(client, "editMessageText", chat_id=chat_id, message_id=message_id,
                       text=to_html(text), parse_mode="HTML", disable_web_page_preview=True)
        else:
            await call(client, "editMessageText", chat_id=chat_id, message_id=message_id, text=text)
    except TelegramError as e:
        if "not modified" in str(e):
            return
        if formatted:  # HTML refusé : texte brut
            await edit_text(client, chat_id, message_id, text, formatted=False)
        else:
            log.warning("édition impossible : %s", e)


# ---------------------------------------------------------------- Markdown → HTML Telegram


def _inline(t: str) -> str:
    codes: list[str] = []

    def keep(m):
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"

    t = re.sub(r"`([^`\n]+)`", keep, t)
    t = html.escape(t, quote=False)
    t = re.sub(r"\*\*([^*\n]+)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"__([^_\n]+)__", r"<b>\1</b>", t)
    t = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", t)
    t = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"<i>\1</i>", t)
    t = re.sub(r"~~([^~\n]+)~~", r"<s>\1</s>", t)
    t = re.sub(r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)", r'<a href="\2">\1</a>', t)
    return re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{html.escape(codes[int(m.group(1))], quote=False)}</code>", t)


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _table(rows: list[list[str]]) -> str:
    """Telegram n'affiche pas les tableaux : on les aligne dans un bloc à chasse fixe."""
    rows = [[re.sub(r"\*\*|__|`", "", c) for c in r] for r in rows]
    n = max(len(r) for r in rows)
    rows = [r + [""] * (n - len(r)) for r in rows]
    widths = [min(max(len(r[i]) for r in rows), 28) for i in range(n)]
    out = []
    for k, r in enumerate(rows):
        out.append(" │ ".join(c[:28].ljust(widths[i]) for i, c in enumerate(r)).rstrip())
        if k == 0:
            out.append("─┼─".join("─" * w for w in widths))
    return "<pre>" + html.escape("\n".join(out), quote=False) + "</pre>"


def to_html(src: str) -> str:
    lines = src.replace("\r", "").split("\n")
    out: list[str] = []
    i = 0
    is_row = lambda l: re.match(r"^\s*\|.*\|\s*$", l) is not None  # noqa: E731
    is_sep = lambda l: re.match(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$", l) is not None  # noqa: E731
    while i < len(lines):
        line = lines[i]
        if re.match(r"^\s*```", line):
            buf = []
            i += 1
            while i < len(lines) and not re.match(r"^\s*```", lines[i]):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append("<pre>" + html.escape("\n".join(buf), quote=False) + "</pre>")
            continue
        if is_row(line) and i + 1 < len(lines) and is_sep(lines[i + 1]):
            rows = [_cells(line)]
            i += 2
            while i < len(lines) and is_row(lines[i]):
                rows.append(_cells(lines[i]))
                i += 1
            out.append(_table(rows))
            continue
        m = re.match(r"^\s*#{1,6}\s+(.*)$", line)
        if m:
            out.append(f"<b>{_inline(m.group(1))}</b>")
        elif re.match(r"^\s*([-*_])\s*\1\s*\1[\s\1]*$", line):
            out.append("──────────")
        elif (m := re.match(r"^(\s*)[-*+]\s+(.*)$", line)):
            out.append(f"{m.group(1)}• {_inline(m.group(2))}")
        elif (m := re.match(r"^\s*>\s?(.*)$", line)):
            out.append(f"<i>{_inline(m.group(1))}</i>")
        else:
            out.append(_inline(line))
        i += 1
    return "\n".join(out).strip()[:LIMIT]


def split_long(text: str) -> list[str]:
    parts, cur = [], ""
    for para in text.split("\n\n"):
        if len(cur) + len(para) + 2 > LIMIT and cur:
            parts.append(cur)
            cur = para
        else:
            cur = f"{cur}\n\n{para}" if cur else para
    parts.append(cur)
    return [p[i:i + LIMIT] for p in parts for i in range(0, len(p), LIMIT)]


# ---------------------------------------------------------------- envoi sortant


async def broadcast(text: str) -> bool:
    """Envoie un message à tous les utilisateurs autorisés (rappels…)."""
    if not enabled() or not TELEGRAM_ALLOWED:
        return False
    ok = False
    async with httpx.AsyncClient(timeout=15) as client:
        for chat_id in TELEGRAM_ALLOWED:
            try:
                await send_text(client, chat_id, text)
                ok = True
            except (TelegramError, httpx.HTTPError) as e:
                log.warning("envoi Telegram à %s impossible : %s", chat_id, e)
    return ok


def conversation_for(chat_id: int) -> int | None:
    v = db.kv_get(f"tg_conv:{chat_id}")
    cid = int(v) if v and v.isdigit() else None
    return cid if cid and db.conversation_exists(cid) else None


# ---------------------------------------------------------------- traitement d'un message


async def keep_typing(client, chat_id: int, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await call(client, "sendChatAction", chat_id=chat_id, action="typing")
        except (TelegramError, httpx.HTTPError):
            pass
        try:
            await asyncio.wait_for(stop.wait(), timeout=4.5)
        except asyncio.TimeoutError:
            pass


async def handle_command(client, chat_id: int, text: str) -> None:
    cmd, _, args = text.partition(" ")
    cmd = cmd.split("@")[0].lower()
    if cmd in ("/start", "/aide", "/help"):
        await send_text(client, chat_id, HELP)
    elif cmd == "/nouveau":
        db.kv_set(f"tg_conv:{chat_id}", "")
        await send_text(client, chat_id, "✨ Nouvelle conversation. Je t'écoute.")
    elif cmd == "/rappels":
        from .reminders import human

        rows = db.list_reminders("pending", limit=30)
        txt = "\n".join(f"• #{r['id']} {human(r['due_at'])} — {r['text']}" for r in rows)
        await send_text(client, chat_id, f"**Rappels programmés**\n\n{txt}" if rows else "Aucun rappel programmé.")
    elif cmd == "/souvenirs":
        rows = db.list_memories()
        txt = "\n".join(f"• {m['content']}" for m in rows[-40:])
        await send_text(client, chat_id,
                        f"**Ce que je sais de toi**\n\n{txt}\n\n_Modifiable depuis l'interface web._"
                        if rows else "Je n'ai encore rien retenu sur toi.")
    elif cmd == "/agent":
        import sys

        from . import tgagent
        await tgagent.start(sys.modules[__name__], client, chat_id, args.strip())
    elif cmd == "/serveur":
        from . import proxmox

        await proxmox.poll()
        await send_text(client, chat_id, "**Serveur Proxmox**\n\n" + proxmox.summary())
    else:
        await send_text(client, chat_id, "Commande inconnue. /aide pour la liste.")


async def handle_message(client, msg: dict) -> None:
    chat_id = msg["chat"]["id"]
    user_id = msg.get("from", {}).get("id")
    text = (msg.get("text") or "").strip()

    if user_id not in TELEGRAM_ALLOWED:
        log.warning("message Telegram refusé de %s (%s)", user_id, msg.get("from", {}).get("username"))
        await send_text(
            client, chat_id,
            f"Je ne te connais pas encore. Ton identifiant Telegram est `{user_id}`.\n"
            "Ajoute-le à ATOM_TELEGRAM_ALLOWED dans le fichier .env d'Atom, puis relance-le.",
        )
        return
    if not text:
        await send_text(client, chat_id, "Je ne lis que le texte pour l'instant.")
        return
    if text.startswith("/"):
        await handle_command(client, chat_id, text)
        return
    # Réponse au résultat de l'agent : on poursuit la même tâche
    from . import tgagent
    rid = tgagent.run_for_reply(chat_id, msg.get("reply_to_message"))
    if rid:
        import sys
        await tgagent.start(sys.modules[__name__], client, chat_id, text, parent=rid)
        return

    stop_typing = asyncio.Event()
    typing = asyncio.create_task(keep_typing(client, chat_id, stop_typing))
    reply, notes, sent, last_edit = "", [], None, 0.0
    persona = db.kv_get("persona") or DEFAULT_PERSONA
    model = db.kv_get("model") or DEFAULT_MODEL
    try:
        async for ev in agent.chat_events(text, conversation_for(chat_id), model, persona, True, "Telegram · "):
            t = ev["type"]
            if t == "meta":
                db.kv_set(f"tg_conv:{chat_id}", str(ev["conversation_id"]))
            elif t == "emotion" and ev["emotion"] in REACTIONS:
                try:
                    await call(client, "setMessageReaction", chat_id=chat_id, message_id=msg["message_id"],
                               reaction=[{"type": "emoji", "emoji": REACTIONS[ev["emotion"]]}])
                except (TelegramError, httpx.HTTPError):
                    pass
            elif t == "token":
                reply += ev["text"]
                now = time.monotonic()
                if sent is None and reply.strip():
                    stop_typing.set()
                    sent = await call(client, "sendMessage", chat_id=chat_id, text=reply.strip()[:LIMIT] + " …")
                    last_edit = now
                elif sent and now - last_edit > EDIT_EVERY and len(reply) < LIMIT:
                    await edit_text(client, chat_id, sent["message_id"], reply.strip() + " …", formatted=False)
                    last_edit = now
            elif t == "reminder":
                if ev["action"] == "created":
                    notes.append(f"⏰ _Rappel programmé : {ev['when']} — {ev['text']}_")
                elif ev["action"] == "cancelled":
                    notes.append(f"_Rappel #{ev['id']} annulé._")
                else:
                    notes.append(f"⚠ _{ev['message']}_")
            elif t == "done":
                stop_typing.set()
                final = (reply.strip() or "…") + ("\n\n" + "\n".join(notes) if notes else "")
                parts = split_long(final)
                if sent:
                    await edit_text(client, chat_id, sent["message_id"], parts[0], formatted=True)
                else:
                    await send_text(client, chat_id, parts[0])
                for p in parts[1:]:
                    await send_text(client, chat_id, p)
                # La mémorisation continue ensuite en arrière-plan.
            elif t == "error":
                stop_typing.set()
                await send_text(client, chat_id, f"⚠ {ev['message']}")
    except Exception as e:  # noqa: BLE001
        log.exception("erreur Telegram")
        try:
            await send_text(client, chat_id, f"⚠ Erreur : {e}")
        except Exception:  # noqa: BLE001
            pass
    finally:
        stop_typing.set()
        typing.cancel()


# ---------------------------------------------------------------- boucle principale


async def run() -> None:
    if not enabled():
        log.info("Telegram désactivé (ATOM_TELEGRAM_TOKEN vide)")
        return
    if not TELEGRAM_ALLOWED:
        log.warning("ATOM_TELEGRAM_ALLOWED est vide : tous les messages seront refusés "
                    "(le bot répondra avec l'identifiant à ajouter).")
    offset = 0
    queue: asyncio.Queue[dict] = asyncio.Queue()

    async with httpx.AsyncClient(timeout=httpx.Timeout(15, read=70)) as client:
        try:
            me = await call(client, "getMe")
            log.info("bot Telegram connecté : @%s", me.get("username"))
            await call(client, "setMyCommands", commands=[
                {"command": "nouveau", "description": "Nouvelle conversation"},
                {"command": "rappels", "description": "Rappels programmés"},
                {"command": "souvenirs", "description": "Ce qu'Atom sait de toi"},
                {"command": "agent", "description": "Confier une tâche à l'agent de code"},
                {"command": "serveur", "description": "État du serveur Proxmox"},
                {"command": "aide", "description": "Aide"},
            ])
        except (TelegramError, httpx.HTTPError) as e:
            log.error("connexion Telegram impossible : %s", e)

        async def worker():
            # Un message à la fois : le modèle tourne sur CPU.
            while True:
                m = await queue.get()
                await handle_message(client, m)

        w = asyncio.create_task(worker())
        try:
            while True:
                try:
                    updates = await call(client, "getUpdates", offset=offset, timeout=50,
                                         allowed_updates=["message", "callback_query"])
                except (TelegramError, httpx.HTTPError) as e:
                    log.warning("getUpdates : %s — nouvel essai dans 10 s", e)
                    await asyncio.sleep(10)
                    continue
                for u in updates or []:
                    offset = u["update_id"] + 1
                    if "message" in u:
                        await queue.put(u["message"])
                    elif "callback_query" in u:   # boutons (agent : diff, appliquer, commit…)
                        cq = u["callback_query"]
                        if cq.get("from", {}).get("id") in TELEGRAM_ALLOWED and cq.get("message"):
                            import sys

                            from . import tgagent
                            asyncio.create_task(tgagent.on_button(sys.modules[__name__], client, cq))
        finally:
            w.cancel()
