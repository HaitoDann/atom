"""Consommation des modèles, routage intelligent et observabilité."""

import json

from conftest import chat


def test_calls_are_journaled_and_summarized(client):
    from app import usage

    def local_ok():
        return next((s["ok"] for s in usage.summary() if s["provider"] == "local"), 0)
    before, ok_before = sum(s["calls"] for s in usage.summary()), local_ok()
    chat(client, "Bonjour")
    assert sum(s["calls"] for s in usage.summary()) == before + 1
    assert local_ok() == ok_before + 1          # l'appel du chat est compté comme réussi
    r = client.get("/api/usage").json()
    assert {"summary", "providers", "timeline", "recent", "prefs", "tasks"} <= set(r)
    assert r["recent"][0]["provider"] == "local"


def test_fallback_is_recorded(client, monkeypatch):
    import asyncio

    from app import providers, usage

    a = providers.Provider("pa", "A", "http://a", "k", "m-a", 100, "llama", 3, True)
    b = providers.Provider("pb", "B", "http://b", "k", "m-b", 100, "qwen", 2, True)

    async def fake_stream(p, messages, model=None, stats=None, max_tokens=None):
        if p.id == "pa":
            raise providers.Unavailable("A en panne")
        stats.update(tokens=5, prompt_tokens=7, model="m-b")
        yield "ok"

    monkeypatch.setattr(providers, "stream", fake_stream)

    async def go():
        used = {}
        return [t async for t in providers.stream_chain([a, b], [{"role": "user", "content": "x"}], used,
                                                         task="simple", reason="test")], used

    out, used = asyncio.run(go())
    assert out == ["ok"] and used["id"] == "pb"
    last = usage.recent(2)
    assert last[0]["provider"] == "pb" and last[0]["fallback_from"] == "pa" and "bascule" in last[0]["reason"]
    assert last[0]["completion_tokens"] == 5 and last[0]["prompt_tokens"] == 7
    assert last[1]["provider"] == "pa" and not last[1]["ok"] and "panne" in last[1]["error"]


def test_routing_by_task(monkeypatch):
    from app import providers

    fast = providers.Provider("fast", "Rapide", "u", "k", "llama-8b", 100, "llama", 1, True)
    strong = providers.Provider("strong", "Fort", "u", "k", "qwen-coder", 100, "qwen", 3, True)
    monkeypatch.setattr(providers, "ALL", [fast, strong])
    monkeypatch.setattr(providers, "HEALTH", {"fast": {"lat": 0.4, "recent": [1] * 5, "consec": 0},
                                              "strong": {"lat": 6.0, "recent": [1] * 5, "consec": 0}})
    monkeypatch.setattr(providers, "route_prefs", lambda: {})
    assert providers.chain(task="simple")[0].id == "fast"       # question courte : le plus rapide
    assert providers.chain(task="complexe")[0].id == "strong"   # demande complexe : le plus fort
    assert providers.chain(task="code")[0].id == "strong"
    # requête trop longue pour l'offre du rapide : il passe derrière
    monkeypatch.setattr(providers, "BUDGETS", {"fast": 2000, "strong": 100000})
    rows = providers.plan(task="simple", est_tokens=50000)
    assert rows[0]["provider"].id == "strong" and any("trop longue" in w for w in rows[1]["why"])
    # préférence de l'utilisateur
    monkeypatch.setattr(providers, "route_prefs", lambda: {"complexe": "fast"})
    assert providers.chain(task="complexe")[0].id == "fast"


def test_quota_pressure_spreads_load(monkeypatch):
    from app import providers

    a = providers.Provider("qa", "A", "u", "k", "m", 100, "llama", 2, True)
    b = providers.Provider("qb", "B", "u", "k", "m", 100, "llama", 2, True)
    monkeypatch.setattr(providers, "ALL", [a, b])
    monkeypatch.setattr(providers, "HEALTH", {})
    monkeypatch.setattr(providers, "route_prefs", lambda: {})
    monkeypatch.setattr(providers, "quota_left", lambda pid: 3 if pid == "qa" else 90)
    rows = providers.plan(task="complexe")
    assert rows[0]["provider"].id == "qb" and any("quota" in w for w in rows[1]["why"])


def test_route_preview_and_prefs(client):
    r = client.post("/api/usage/route", json={"message": "Corrige ce bug dans ma fonction python"}).json()
    assert r["task"] == "code" and r["order"] and r["order"][0]["why"] is not None
    pid = r["order"][0]["id"]
    assert client.put("/api/usage/routing", json={"prefs": {"code": pid, "inconnu": "x"}}).json()["prefs"] == {"code": pid}
    assert client.get("/api/usage").json()["prefs"] == {"code": pid}
    client.put("/api/usage/routing", json={"prefs": {}})


def test_live_stream_starts_with_snapshot(client):
    from app import usage

    q = usage.subscribe()
    usage.record("local", model="m", ok=True, completion_tokens=3)
    ev = q.get_nowait()
    usage.unsubscribe(q)
    assert ev["type"] == "call" and ev["completion_tokens"] == 3


def test_metrics(client, monkeypatch):
    chat(client, "Bonjour")
    r = client.get("/api/metrics")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
    body = r.text
    assert 'atom_model_calls_total{provider="local",result="ok"}' in body
    assert "atom_http_request_duration_seconds_bucket" in body and "atom_provider_quota_remaining" in body
    assert r.headers.get("x-request-id")
    # sans session : refusé, sauf jeton Prometheus
    from fastapi.testclient import TestClient

    from app import main, observability
    anon = TestClient(main.app)
    assert anon.get("/api/metrics").status_code == 401
    monkeypatch.setattr(observability, "METRICS_TOKEN", "jeton-test")
    assert anon.get("/api/metrics", headers={"Authorization": "Bearer jeton-test"}).status_code == 200
    assert anon.get("/api/metrics", headers={"Authorization": "Bearer faux"}).status_code == 401


def test_request_id_propagated(client):
    r = client.get("/api/usage", headers={"X-Request-ID": "abc-123"})
    assert r.headers["x-request-id"] == "abc-123"
    r = client.get("/api/usage", headers={"X-Request-ID": "<script>"})
    assert r.headers["x-request-id"] != "<script>"


def test_json_logs():
    import logging

    from app.observability import JsonFormatter, request_id

    tok = request_id.set("rid-1")
    rec = logging.LogRecord("atom.x", logging.INFO, __file__, 1, "bonjour %s", ("toi",), None)
    rec.request_id = "rid-1"
    rec.provider = "groq"
    out = json.loads(JsonFormatter().format(rec))
    request_id.reset(tok)
    assert out["msg"] == "bonjour toi" and out["request_id"] == "rid-1" and out["provider"] == "groq"
