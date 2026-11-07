"""Canaux sortants et recherche web : Telegram, ntfy, SearXNG — sans réseau (transports simulés)."""

import asyncio
import json

import httpx
import pytest


def run(coro):
    return asyncio.run(coro)


def fake_client_factory(handler):
    """Remplace httpx.AsyncClient : même interface, réponses fournies par `handler`."""
    real = httpx.AsyncClient

    def make(*args, **kw):
        kw.pop("transport", None)
        return real(*args, transport=httpx.MockTransport(handler), **kw)

    return make


# ---------------------------------------------------------------- Telegram : mise en forme


def test_to_html_markdown():
    from app.telegram import to_html

    out = to_html("# Titre\n**gras** et *italique* `x<y`\n- puce\n> citation\n[lien](https://a.fr)\n---")
    assert "<b>Titre</b>" in out
    assert "<b>gras</b>" in out and "<i>italique</i>" in out
    assert "<code>x&lt;y</code>" in out
    assert "• puce" in out and "<i>citation</i>" in out
    assert '<a href="https://a.fr">lien</a>' in out
    assert "──────────" in out


def test_to_html_code_block_and_table():
    from app.telegram import to_html

    out = to_html("```\n<b>brut</b>\n```\n| A | B |\n|---|---|\n| 1 | **2** |")
    assert "<pre>&lt;b&gt;brut&lt;/b&gt;</pre>" in out
    assert "│" in out and "─┼─" in out and "**" not in out


def test_split_long():
    from app.telegram import LIMIT, split_long

    parts = split_long("a" * 100 + "\n\n" + "b" * LIMIT + "\n\n" + "c" * (LIMIT * 2 + 5))
    assert all(len(p) <= LIMIT for p in parts)
    assert "".join(parts).replace("\n", "") == "a" * 100 + "b" * LIMIT + "c" * (LIMIT * 2 + 5)


# ---------------------------------------------------------------- Telegram : API


def _tg_handler(calls, refuse_html=False, fail=None):
    def handler(req: httpx.Request):
        method = req.url.path.rsplit("/", 1)[-1]
        body = json.loads(req.content or b"{}")
        calls.append((method, body))
        if fail and method in fail:
            return httpx.Response(200, json={"ok": False, "description": fail[method]})
        if refuse_html and body.get("parse_mode") == "HTML":
            return httpx.Response(200, json={"ok": False, "description": "can't parse entities"})
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
    return handler


def test_send_text_falls_back_to_plain():
    from app import telegram

    calls = []

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(_tg_handler(calls, refuse_html=True))) as c:
            return await telegram.send_text(c, 42, "**salut**")

    assert run(go()) == {"message_id": 1}
    assert [m for m, _ in calls] == ["sendMessage", "sendMessage"]
    assert "parse_mode" not in calls[1][1] and calls[1][1]["text"] == "**salut**"


def test_call_raises_on_error():
    from app import telegram

    async def go():
        handler = _tg_handler([], fail={"getMe": "Unauthorized"})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            await telegram.call(c, "getMe")

    with pytest.raises(telegram.TelegramError, match="Unauthorized"):
        run(go())


def test_edit_text_paths():
    from app import telegram

    calls = []

    async def go(handler):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            await telegram.edit_text(c, 1, 2, "**x**", formatted=True)

    run(go(_tg_handler(calls, refuse_html=True)))          # HTML refusé → texte brut
    assert len(calls) == 2 and "parse_mode" not in calls[1][1]
    calls.clear()
    run(go(_tg_handler(calls, fail={"editMessageText": "message is not modified"})))
    assert len(calls) == 1                                  # « not modified » : on s'arrête là


def test_handle_command(client):
    from app import db, telegram

    db.kv_set("tg_conv:7", "123")
    calls = []

    async def go(text):
        async with httpx.AsyncClient(transport=httpx.MockTransport(_tg_handler(calls))) as c:
            await telegram.handle_command(c, 7, text)

    for cmd in ("/aide", "/nouveau", "/rappels", "/souvenirs", "/inconnue@AtomBot"):
        run(go(cmd))
    texts = [b["text"] for _, b in calls]
    assert any("Nouvelle conversation" in t for t in texts)
    assert any("Commande inconnue" in t for t in texts)
    assert db.kv_get("tg_conv:7") == ""


def test_handle_message_refuses_unknown_user(client, monkeypatch):
    from app import telegram

    monkeypatch.setattr(telegram, "TELEGRAM_ALLOWED", {1})
    calls = []

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(_tg_handler(calls))) as c:
            await telegram.handle_message(c, {"chat": {"id": 9}, "from": {"id": 9}, "text": "salut"})

    run(go())
    assert all(b.get("chat_id") != 1 for _, b in calls)
    assert not any(m == "sendChatAction" for m, _ in calls)   # aucun traitement lancé


def test_broadcast(monkeypatch):
    from app import telegram

    assert run(telegram.broadcast("x")) is False             # pas de jeton en test
    calls = []
    monkeypatch.setattr(telegram, "TELEGRAM_TOKEN", "t")
    monkeypatch.setattr(telegram, "TELEGRAM_ALLOWED", {1, 2})
    monkeypatch.setattr(telegram.httpx, "AsyncClient", fake_client_factory(_tg_handler(calls, fail={})))
    assert run(telegram.broadcast("rappel")) is True
    assert sorted(b["chat_id"] for _, b in calls) == [1, 2]


# ---------------------------------------------------------------- ntfy


def test_ascii_header():
    from app.notify import _ascii_header

    assert _ascii_header("Rappel") == "Rappel"
    assert _ascii_header("Café ☕").startswith("=?UTF-8?B?")


@pytest.mark.parametrize("status,expected", [(200, True), (500, False)])
def test_ntfy(monkeypatch, status, expected):
    from app import notify

    seen = {}

    def handler(req):
        seen.update(url=str(req.url), headers=req.headers, body=req.content.decode())
        return httpx.Response(status, text="ok")

    monkeypatch.setattr(notify, "NTFY_URL", "http://ntfy")
    monkeypatch.setattr(notify, "PUBLIC_URL", "https://atom.example")
    monkeypatch.setattr(notify.httpx, "AsyncClient", fake_client_factory(handler))
    assert run(notify.send("Rappel ☕", "appeler le garage", conversation_id=5, tags="bell")) is expected
    assert seen["url"].endswith("/atom") and seen["body"] == "appeler le garage"
    assert seen["headers"]["Click"] == "https://atom.example/?c=5" and seen["headers"]["Tags"] == "bell"


def test_ntfy_unreachable(monkeypatch):
    from app import notify

    def handler(req):
        raise httpx.ConnectError("refusé", request=req)

    monkeypatch.setattr(notify, "NTFY_URL", "http://ntfy")
    monkeypatch.setattr(notify.httpx, "AsyncClient", fake_client_factory(handler))
    assert run(notify.send("t", "b")) is False


# ---------------------------------------------------------------- recherche web


def test_page_text_keeps_content_only():
    from app.search import page_text

    raw = ("<html><head><title>T</title><script>var x=1</script></head><body><nav>Accueil</nav>"
           "<p>Une phrase de contenu suffisamment longue pour être retenue par le filtre.</p>"
           "<footer>Mentions légales et autres liens très longs à ignorer ici</footer></body></html>")
    out = page_text(raw)
    assert "contenu suffisamment longue" in out
    assert "var x" not in out and "Accueil" not in out and "Mentions" not in out


def test_search(monkeypatch):
    from app import search

    page = "<p>" + "Contenu lu sur la page, assez long pour passer le filtre de lignes. " * 2 + "</p>"

    def handler(req):
        if req.url.path == "/search":
            return httpx.Response(200, json={"results": [
                {"title": "Un", "url": "https://www.un.fr/a", "content": "extrait"},
                {"title": "Pas web", "url": "ftp://x"},
            ]})
        return httpx.Response(200, text=page, headers={"content-type": "text/html"})

    monkeypatch.setattr(search, "SEARXNG_URL", "http://searxng")
    monkeypatch.setattr(search, "_public_host", lambda host: True)
    monkeypatch.setattr(search.httpx, "AsyncClient", fake_client_factory(handler))
    res = run(search.search("atom"))
    assert len(res) == 1 and res[0]["domain"] == "un.fr" and res[0]["snippet"] == "extrait"
    assert "Contenu lu sur la page" in res[0]["content"]


def test_search_refuses_private_addresses(monkeypatch):
    from app import search

    assert search._public_host("127.0.0.1") is False
    assert search._public_host("192.168.1.10") is False
    req = httpx.Request("GET", "http://localhost/")
    with pytest.raises(httpx.RequestError):
        run(search._check_request(req))


def test_search_disabled_and_error(monkeypatch):
    from app import search

    with pytest.raises(RuntimeError, match="pas configurée"):
        run(search.search("x"))
    monkeypatch.setattr(search, "SEARXNG_URL", "http://searxng")
    monkeypatch.setattr(search.httpx, "AsyncClient", fake_client_factory(lambda r: httpx.Response(503)))
    with pytest.raises(RuntimeError, match="503"):
        run(search.search("x"))
