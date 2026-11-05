"""Recherche web via SearXNG auto-hébergé, puis lecture des meilleures pages."""

from __future__ import annotations

import asyncio
import html
import logging
import re
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

from .config import SEARCH_PAGES, SEARCH_RESULTS, SEARXNG_URL

log = logging.getLogger("atom.search")
UA = "Mozilla/5.0 (X11; Linux x86_64) AtomAssistant/1.0"


def enabled() -> bool:
    return bool(SEARXNG_URL)


class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "aside", "iframe"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.depth = 0
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.depth += 1
        if tag == "title":
            self._in_title = True
        if tag in ("p", "br", "li", "h1", "h2", "h3", "h4", "tr", "div"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth:
            self.depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.depth:
            self.parts.append(data)


def page_text(raw: str, limit: int = 2500) -> str:
    p = _Text()
    try:
        p.feed(raw)
    except Exception:  # noqa: BLE001 — HTML cassé : on garde ce qu'on a
        pass
    text = html.unescape("".join(p.parts))
    lines = [re.sub(r"[ \t ]+", " ", l).strip() for l in text.split("\n")]
    # On garde les lignes qui ressemblent à du contenu (pas les menus d'un mot).
    lines = [l for l in lines if len(l) > 40 or (len(l) > 15 and l.endswith((".", ":", "!", "?")))]
    return "\n".join(lines)[:limit]


async def _fetch(client: httpx.AsyncClient, url: str) -> str:
    try:
        r = await client.get(url, headers={"User-Agent": UA, "Accept-Language": "fr,en;q=0.8"})
        if r.status_code >= 400 or "html" not in r.headers.get("content-type", ""):
            return ""
        return page_text(r.text[:600_000])
    except (httpx.HTTPError, UnicodeDecodeError):
        return ""


async def search(query: str) -> list[dict]:
    """Résultats : [{title, url, domain, snippet, content}] — content = extrait de la page lue."""
    if not enabled():
        raise RuntimeError("La recherche web n'est pas configurée (service searxng).")
    async with httpx.AsyncClient(timeout=httpx.Timeout(8, read=12), follow_redirects=True) as client:
        r = await client.get(f"{SEARXNG_URL}/search",
                             params={"q": query, "format": "json", "language": "fr", "safesearch": 1})
        if r.status_code != 200:
            raise RuntimeError(f"SearXNG a répondu {r.status_code}")
        items = r.json().get("results", [])[:SEARCH_RESULTS]
        results = [{
            "title": (it.get("title") or it.get("url", "")).strip()[:160],
            "url": it.get("url", ""),
            "domain": urlparse(it.get("url", "")).netloc.removeprefix("www."),
            "snippet": (it.get("content") or "").strip()[:400],
            "content": "",
        } for it in items if it.get("url", "").startswith("http")]
        pages = await asyncio.gather(*[_fetch(client, x["url"]) for x in results[:SEARCH_PAGES]])
        for x, content in zip(results, pages):
            x["content"] = content
    log.info("recherche « %s » : %d résultats", query, len(results))
    return results


def prompt_block(query: str, results: list[dict], today: str) -> str:
    lines = [f"Résultats d'une recherche web pour « {query} » (faite le {today}) :", ""]
    for i, r in enumerate(results, 1):
        body = r["content"] or r["snippet"]
        lines.append(f"[{i}] {r['title']} — {r['domain']}\n{body}\n")
    lines.append(
        "Réponds à la question en t'appuyant sur ces résultats. Cite tes sources avec leur numéro, "
        "par exemple [1]. Si les résultats ne permettent pas de répondre, dis-le simplement."
    )
    return "\n".join(lines)
