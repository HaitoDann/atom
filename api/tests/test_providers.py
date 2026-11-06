import asyncio

import pytest

from app import providers, workshop
from app.providers import Provider


@pytest.fixture
def three(monkeypatch):
    ps = [Provider("groq", "Groq", "u", "k", "llama-3.3-70b", 100, "llama", 3, True),
          Provider("cerebras", "Cerebras", "u", "k", "qwen-3-235b", 100, "qwen", 3, True),
          Provider("gemini", "Gemini", "u", "k", "gemini-2.5-flash", 100, "gemini", 3, False)]
    monkeypatch.setattr(providers, "ALL", ps)
    monkeypatch.setattr(providers, "_cooldown", {})
    return ps


def test_assign_roles(three):
    r = workshop.assign("review", ["auto", "auto", "auto"])
    assert r[0] == r[2] and workshop._info(r[1])[1] != workshop._info(r[0])[1]
    p = workshop.assign("panel", ["auto", "auto", "auto"])
    assert len(set(p)) == 3 and "local" not in p              # arbitre : un troisième fournisseur fort
    assert workshop.assign("panel", ["local", "auto", "auto"])[2] != "local"
    assert workshop.warnings("panel", ["auto", "auto", "local"])   # arbitre faible signalé


def test_privacy_and_family(three):
    assert [p.id for p in providers.chain(sensitive=True)] == ["groq", "cerebras"]
    assert providers.family_of("meta-llama/llama-4-scout") == "llama"
    assert providers.family_of("openai/gpt-oss-120b") == "gpt"


def test_fallback(three, monkeypatch):
    real = providers.stream

    async def fake(p, messages, model=None, stats=None):
        if p.id == "groq":
            raise providers.Unavailable("limite de l'offre Groq atteinte")
            yield  # noqa
        async for t in real(p, messages, model, stats):
            yield t

    monkeypatch.setattr(providers, "stream", fake)

    async def go():
        used = {}
        out = [t async for t in providers.stream_chain(providers.chain("groq"), [{"role": "system", "content": "x"}, {"role": "user", "content": "y"}], used)]
        return "".join(out), used

    text, used = asyncio.run(go())
    assert used["id"] == "cerebras" and "Groq" in used["skipped"][0] and "Cerebras" in text


def test_review_ok():
    assert workshop.review_ok("…\nNon vérifiable : rien.\nVerdict : OK")
    assert not workshop.review_ok("- [important] Exactitude : date fausse\nVerdict : OK")
    assert not workshop.review_ok("Verdict : À corriger")


def test_workshop_skips_correction(three, client):
    client.put("/api/workshop", json={"enabled": True, "pattern": "review", "participants": ["p:groq", "p:cerebras", "auto"]})
    lines = client.post("/api/workshop/run", json={"message": "Explique le DNS"}).text.splitlines()
    assert any('"Validée"' in l for l in lines) and any('"done"' in l and '"final"' in l for l in lines)
    w = client.get("/api/workshop").json()
    assert w["assigned"][1].startswith("Cerebras") and any(o["id"] == "p:gemini" for o in w["options"])
