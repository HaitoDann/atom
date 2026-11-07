"""Modèle local (Ollama) : flux, erreurs, JSON contraint, embeddings — réponses simulées, appels journalisés."""

import asyncio
import json

import httpx
import pytest


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def ollama(client, monkeypatch):
    from app import llm

    monkeypatch.setattr(llm, "PROVIDER", "ollama")
    real = httpx.AsyncClient

    def install(handler):
        def make(*a, **kw):
            kw.pop("transport", None)
            return real(*a, transport=httpx.MockTransport(handler), **kw)
        monkeypatch.setattr(llm.httpx, "AsyncClient", make)
    return install


def ndjson(*objs):
    return "\n".join(json.dumps(o) for o in objs) + "\n"


def stream(model="qwen3:4b", messages=None):
    from app import llm

    async def go():
        return "".join([t async for t in llm.stream_chat(model, messages or [{"role": "user", "content": "x"}], task="simple")])
    return run(go())


def test_stream_ok_with_stats(ollama):
    from app import llm, usage

    seen = {}

    def handler(req):
        seen.update(json.loads(req.content))
        return httpx.Response(200, text=ndjson(
            {"message": {"content": "Bon"}}, {"message": {"content": "jour"}},
            {"done": True, "eval_count": 8, "eval_duration": 2e9, "prompt_eval_count": 30, "prompt_eval_duration": 1e9,
             "load_duration": 1e8, "total_duration": 3e9}))
    ollama(handler)
    assert stream() == "Bonjour"
    assert seen["model"] == "qwen3:4b" and seen["stream"] is True and seen["think"] is False
    assert llm.last_stats["tokens"] == 8 and llm.last_stats["tok_s"] == 4.0 and llm.last_stats["prompt_tokens"] == 30
    rec = usage.recent(1)[0]
    assert rec["provider"] == "local" and rec["ok"] and rec["task"] == "simple"
    assert rec["completion_tokens"] == 8 and rec["prompt_tokens"] == 30


def test_stream_model_missing(ollama):
    from app import llm, usage

    ollama(lambda r: httpx.Response(404, text='{"error":"model \\"qwen9\\" not found"}'))
    with pytest.raises(llm.ModelMissing, match="ollama pull qwen9"):
        stream("qwen9")
    rec = usage.recent(1)[0]
    assert rec["provider"] == "local" and not rec["ok"] and "pas installé" in rec["error"]


def test_stream_error_chunk_and_server_error(ollama):
    ollama(lambda r: httpx.Response(200, text=ndjson({"error": "out of memory"})))
    with pytest.raises(RuntimeError, match="out of memory"):
        stream()
    ollama(lambda r: httpx.Response(500, text="boom"))
    with pytest.raises(RuntimeError, match="500"):
        stream()


def test_stream_unreachable(ollama):
    from app import usage

    def down(req):
        raise httpx.ConnectError("refusé", request=req)
    ollama(down)
    with pytest.raises(httpx.ConnectError):
        stream()
    assert "ConnectError" in usage.recent(1)[0]["error"] or "refusé" in usage.recent(1)[0]["error"]


def test_json_chat_recorded(ollama):
    from app import llm, usage

    ollama(lambda r: httpx.Response(200, json={"message": {"content": '<think>…</think>{"faits": ["a"]}'},
                                               "prompt_eval_count": 50, "eval_count": 6}))
    out = run(llm.json_chat("qwen3:4b", [{"role": "user", "content": "x"}], {"type": "object"}))
    assert out == {"faits": ["a"]}
    rec = usage.recent(1)[0]
    assert rec["task"] == "memoire" and rec["prompt_tokens"] == 50 and rec["completion_tokens"] == 6
    ollama(lambda r: httpx.Response(200, json={"message": {"content": "pas du json"}}))
    assert run(llm.json_chat("qwen3:4b", [], {})) == {}


def test_embed_ok_and_failures(ollama):
    from app import llm, usage

    seen = {}

    def handler(req):
        seen.update(json.loads(req.content))
        return httpx.Response(200, json={"embeddings": [[3.0, 4.0], [0.0, 0.0]], "prompt_eval_count": 12})
    ollama(handler)
    vecs = run(llm.embed(["un", "deux"], kind="query"))
    assert seen["input"][0].startswith("search_query: ")
    assert vecs[0].tolist() == pytest.approx([0.6, 0.8]) and vecs[1].tolist() == [0.0, 0.0]
    rec = usage.recent(1)[0]
    assert rec["task"] == "embedding" and rec["ok"] and rec["prompt_tokens"] == 12 and "2 texte" in rec["reason"]

    ollama(lambda r: httpx.Response(500, text="modèle absent"))
    assert run(llm.embed(["x"])) is None
    assert not usage.recent(1)[0]["ok"]

    ollama(lambda r: httpx.Response(200, json={"embeddings": [[1.0]]}))   # nombre de vecteurs incohérent
    assert run(llm.embed(["a", "b"])) is None
    assert run(llm.embed([])) == []


def test_installed_models(ollama):
    from app import llm

    ollama(lambda r: httpx.Response(200, json={"models": [{"name": "qwen3:4b"}, {"name": "nomic-embed-text:latest"}]}))
    assert run(llm.installed_models()) == ["qwen3:4b", "nomic-embed-text:latest"]
