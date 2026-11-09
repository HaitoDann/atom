"""Appels HTTP aux fournisseurs : flux SSE, erreurs, limites, mises en pause et bascule — réponses simulées."""

import asyncio
import json

import httpx
import pytest


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def real_mode(client, monkeypatch):
    """Sort du mode test pour exercer le vrai code HTTP, avec un transport simulé."""
    from app import providers

    monkeypatch.setattr(providers, "PROVIDER", "openai")
    monkeypatch.setattr(providers, "_cooldown", {})
    monkeypatch.setattr(providers, "HEALTH", {})

    real = httpx.AsyncClient

    def install(handler):
        def make(*a, **kw):
            kw.pop("transport", None)
            return real(*a, transport=httpx.MockTransport(handler), **kw)
        monkeypatch.setattr(providers.httpx, "AsyncClient", make)
    return install


def prov(pid="px", key="k"):
    from app import providers
    return providers.Provider(pid, pid.upper(), f"https://{pid}.test/v1", key, f"{pid}-model", 100, "llama", 2, True)


def sse(*chunks, usage=None):
    lines = [f"data: {json.dumps({'choices': [{'delta': {'content': c}}]})}" for c in chunks]
    if usage:
        lines.append(f"data: {json.dumps({'choices': [], 'usage': usage})}")
    lines.append("data: [DONE]")
    return "\n\n".join(lines) + "\n\n"


def collect(p, stats=None, messages=None):
    from app import providers

    async def go():
        return "".join([t async for t in providers.stream(p, messages or [{"role": "user", "content": "x"}], stats=stats)])
    return run(go())


def test_stream_sse_with_usage(real_mode):
    seen = {}

    def handler(req):
        seen["auth"] = req.headers["authorization"]
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, text=sse("Bon", "jour", usage={"prompt_tokens": 11, "completion_tokens": 2}))
    real_mode(handler)
    stats = {}
    assert collect(prov(), stats) == "Bonjour"
    assert seen["auth"] == "Bearer k" and seen["body"]["stream"] is True and seen["body"]["model"] == "px-model"
    assert stats["tokens"] == 2 and stats["prompt_tokens"] == 11 and stats["provider"] == "px"


def test_stream_plain_json_body(real_mode):
    real_mode(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "Réponse entière"}}], "usage": {"completion_tokens": 3}}))
    stats = {}
    assert collect(prov(), stats) == "Réponse entière"
    assert stats["tokens"] == 3


@pytest.mark.parametrize("status,body,match,paused", [
    (401, "nope", "clé API", False),
    (429, "rate limit", "limite", True),
    (500, "boom", "a répondu 500", True),
    (404, "model not found", "n'existe pas", True),     # erreur de configuration : écarté 10 min
])
def test_stream_errors(real_mode, status, body, match, paused):
    from app import providers

    real_mode(lambda r: httpx.Response(status, text=body))
    with pytest.raises(providers.Unavailable, match=match):
        collect(prov())
    assert (providers._cooldown.get("px", 0) > 0) is paused   # en pause : plus proposé pendant un moment


def test_stream_empty_and_unreachable(real_mode):
    from app import providers

    real_mode(lambda r: httpx.Response(200, text="data: [DONE]\n\n"))
    with pytest.raises(providers.Unavailable, match="rien répondu"):
        collect(prov())

    def down(req):
        raise httpx.ConnectError("refusé", request=req)
    real_mode(down)
    with pytest.raises(providers.Unavailable, match="injoignable"):
        collect(prov("py"))
    assert providers._cooldown["py"] > 0


def test_chain_falls_back_on_real_errors(real_mode):
    from app import providers, usage

    def handler(req):
        if req.url.host == "pa.test":
            return httpx.Response(429, text="rate limit exceeded")
        return httpx.Response(200, text=sse("relais ", "ok", usage={"prompt_tokens": 5, "completion_tokens": 2}))
    real_mode(handler)
    a, b = prov("pa"), prov("pb")

    async def go():
        used = {}
        out = "".join([t async for t in providers.stream_chain([a, b], [{"role": "user", "content": "x"}], used,
                                                               task="simple", reason="test")])
        return out, used
    out, used = run(go())
    assert out == "relais ok" and used["id"] == "pb" and "limite" in used["skipped"][0]
    assert providers.HEALTH["pa"]["consec"] == 1 and providers.HEALTH["pb"]["consec"] == 0
    rec = usage.recent(2)
    assert rec[0]["provider"] == "pb" and rec[0]["fallback_from"] == "pa" and rec[0]["completion_tokens"] == 2
    # A est en pause : il n'est plus proposé tant que la pause dure
    assert [p.id for p in providers.chain(exclude=set(), task="simple") if p.id in ("pa",)] == []


def test_chain_all_down(real_mode):
    from app import providers

    real_mode(lambda r: httpx.Response(503, text="down"))

    async def go():
        used = {}
        return [t async for t in providers.stream_chain([prov("pa"), prov("pb")], [{"role": "user", "content": "x"}], used)]
    with pytest.raises(providers.Unavailable, match="503"):
        run(go())


def test_chat_tools_success_and_usage(real_mode):
    from app import providers, usage

    msg = {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function",
                                                                  "function": {"name": "list", "arguments": "{}"}}]}
    real_mode(lambda r: httpx.Response(200, json={"choices": [{"message": msg}], "usage": {"prompt_tokens": 40, "completion_tokens": 9}}))
    out = run(providers.chat_tools(prov(), [{"role": "user", "content": "x"}], tools=[]))
    assert out["tool_calls"][0]["function"]["name"] == "list"
    last = usage.recent(1)[0]
    assert last["task"] == "agent" and last["prompt_tokens"] == 40 and last["completion_tokens"] == 9


def test_chat_tools_retries_short_rate_limit(real_mode, monkeypatch):
    from app import providers

    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, text="Please try again in 0.2s", headers={"retry-after": "0.2"})
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]})
    real_mode(handler)

    async def fast_sleep(_):
        return None
    monkeypatch.setattr(providers.asyncio, "sleep", fast_sleep)
    assert run(providers.chat_tools(prov(), [], tools=[]))["content"] == "ok"
    assert calls["n"] == 2


@pytest.mark.parametrize("status,body,exc,match", [
    (429, "Rate limit reached: tokens per day. Please try again in 12m3s", "RateLimited", "du jour"),
    (413, "Request too large", "TooLarge", "trop longue"),
    (400, "maximum context length exceeded", "TooLarge", "trop longue"),
    (403, "forbidden", "Unavailable", "clé API"),
])
def test_chat_tools_errors(real_mode, status, body, exc, match):
    from app import providers, usage

    real_mode(lambda r: httpx.Response(status, text=body))
    with pytest.raises(getattr(providers, exc), match=match):
        run(providers.chat_tools(prov(), [], tools=[]))
    assert usage.recent(1)[0]["ok"] is False


def test_health_restored_from_journal(real_mode, monkeypatch):
    from app import providers, usage

    p = prov("pr")
    monkeypatch.setattr(providers, "ALL", [p])
    for ok in (True, True, False, False, False):
        usage.record("pr", ok=ok, first_s=1.0 if ok else None, error="" if ok else "panne")
    providers.HEALTH.clear()
    providers.restore_health()
    h = providers.HEALTH["pr"]
    assert h["consec"] == 3 and h["recent"][-5:] == [1, 1, 0, 0, 0]
    assert providers.assess(p, "simple")[1]   # la pénalité est expliquée
