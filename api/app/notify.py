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
    return bool(NTFY_URL)


def _ascii_header(v: str) -> str:
    # Les en-têtes HTTP doivent rester en latin-1 : ntfy accepte l'encodage RFC 2047.
    try:
        v.encode("latin-1")
        return v
    except UnicodeEncodeError:
        import base64

        return "=?UTF-8?B?" + base64.b64encode(v.encode()).decode() + "?="


async def send(title: str, body: str, conversation_id: int | None = None, tags: str = "") -> bool:
    if not enabled():
        log.info("ntfy désactivé (ATOM_NTFY_URL vide) — message non envoyé : %s", title)
        return False
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
