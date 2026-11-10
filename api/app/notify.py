"""Canaux sortants : Atom qui t'écrit.

Chaque canal expose `send(title, body, conversation_id)`. Seul ntfy existe pour
l'instant ; une messagerie (Telegram, Discord…) viendra se brancher ici.
"""

from __future__ import annotations

import logging

import httpx

from .config import NTFY_TOKEN, NTFY_TOPIC, NTFY_URL, PUBLIC_URL

log = logging.getLogger("atom.notify")


def enabled() -> bool:
    from . import telegram

    from . import push
    return bool(NTFY_URL) or (telegram.enabled() and bool(telegram.TELEGRAM_ALLOWED)) or push.enabled()


def _ascii_header(v: str) -> str:
    # Les en-têtes HTTP doivent rester en latin-1 : ntfy accepte l'encodage RFC 2047.
    try:
        v.encode("latin-1")
        return v
    except UnicodeEncodeError:
        import base64

        return "=?UTF-8?B?" + base64.b64encode(v.encode()).decode() + "?="


async def send(title: str, body: str, conversation_id: int | None = None, tags: str = "",
               buttons: list[list[tuple[str, str]]] | None = None, url: str | None = None) -> bool:
    """Envoie sur tous les canaux configurés. Vrai si au moins un a réussi.
    buttons : boutons Telegram [[(texte, callback_data)]] (ntfy : lien vers l'interface)."""
    from . import telegram

    markup = {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in buttons]} if buttons else None
    results = [await telegram.broadcast(f"**{title}**\n{body}", markup)]
    if NTFY_URL:
        results.append(await _ntfy(title, body, conversation_id, tags))
    from . import push
    if push.enabled():   # appli Atom installée (téléphone) ou navigateur abonné : notification native
        target = url or ("/?view=agenda" if tags == "calendar" else f"/?c={conversation_id}" if conversation_id else "/")
        try:
            results.append(await push.send(title, body, target, tags, buttons))
        except Exception:   # une panne d'un canal ne bloque pas les autres
            log.warning("notification web impossible", exc_info=True)
    if not any(results):
        log.info("aucun canal n'a pu envoyer : %s", title)
    return any(results)


async def _ntfy(title: str, body: str, conversation_id: int | None, tags: str) -> bool:
    headers = {"Title": _ascii_header(title), "Markdown": "yes"}
    if tags:
        headers["Tags"] = tags
    if PUBLIC_URL:
        headers["Click"] = PUBLIC_URL + (f"/?c={conversation_id}" if conversation_id else "/")
    if NTFY_TOKEN:
        headers["Authorization"] = f"Bearer {NTFY_TOKEN}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{NTFY_URL}/{NTFY_TOPIC}", content=body.encode(), headers=headers)
        if r.status_code >= 300:
            log.warning("ntfy a répondu %s : %s", r.status_code, r.text[:200])
            return False
        return True
    except httpx.HTTPError as e:
        log.warning("ntfy injoignable : %s", e)
        return False
