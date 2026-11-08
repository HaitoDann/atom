"""Lanceur d'atelier : suggestion de schéma, prévisualisation de l'équipe, plan envoyé au départ, durée des étapes."""

import json

import pytest


@pytest.mark.parametrize("text,pattern", [
    ("Faut-il passer à Kubernetes pour mon serveur ?", "debate"),
    ("Docker ou Podman pour mes conteneurs ?", "debate"),
    ("Compare SQLite et PostgreSQL pour Atom", "panel"),
    ("Écris une fonction Python qui trie une liste", "review"),
])
def test_suggest(text, pattern):
    from app import workshop
    assert workshop.suggest(text)[0] == pattern


def test_preview(client):
    r = client.post("/api/workshop/preview", json={"message": "Faut-il passer à Kubernetes ?", "pattern": "review", "rounds": 2}).json()
    assert r["suggested"] == "debate" and r["pattern"] == "review"
    assert [s["role"] for s in r["steps"]] == ["Rédacteur", "Relecteur", "Correction", "Relecteur", "Correction"]
    assert r["calls"] == 5 and all(s["engine"] for s in r["steps"])
    assert len(r["examples"]) >= 3
    r = client.post("/api/workshop/preview", json={"pattern": "panel"}).json()
    assert [s["role"] for s in r["steps"]] == ["Proposition A", "Proposition B", "Arbitre"]


def test_run_without_enabling_and_plan_event(client):
    client.put("/api/workshop", json={"enabled": False})
    with client.stream("POST", "/api/workshop/run", json={"message": "Compare deux options", "pattern": "panel"}) as r:
        assert r.status_code == 200
        events = [json.loads(line) for line in r.iter_lines() if line]
    kinds = [e["type"] for e in events]
    assert "plan" in kinds and kinds.index("plan") < kinds.index("step")
    plan = next(e for e in events if e["type"] == "plan")
    assert [s["role"] for s in plan["steps"]] == ["Proposition A", "Proposition B", "Arbitre"]
    done = [e for e in events if e["type"] == "step" and e["status"] == "done"]
    assert len(done) == 3 and all("seconds" in e for e in done)
    assert events[-1]["type"] == "done"


def test_preview_is_sandboxed(client):
    r = client.post("/api/preview", json={"html": "<!doctype html><h1>Salut</h1><script>1</script>"}).json()
    page = client.get(r["url"])
    assert page.status_code == 200 and "<h1>Salut</h1>" in page.text
    csp = page.headers["content-security-policy"]
    assert csp.startswith("sandbox ") and "allow-same-origin" not in csp     # origine isolée : pas d'accès à Atom
    assert page.headers["x-frame-options"] == "SAMEORIGIN"
    assert client.get("/api/preview/inconnu").status_code == 404


def test_deliverable_prompts():
    from app import workshop
    req = "Crée une page web de présentation de mon entreprise, style Linux Mint, thème rouge"
    writer = workshop._prompts("review", 0, req, [])[0]["content"]
    reviewer = workshop._prompts("review", 1, req, ["v1"])[0]["content"]
    fixer = workshop._prompts("review", 2, req, ["v1", "relecture"])[0]["content"]
    assert "LIVRABLE" in writer and "Lorem" in writer and "responsive" in writer
    assert "5. Livrable" in reviewer and reviewer.count("Termine par") == 1
    assert "COMPLÈTE" in fixer and "LIVRABLE" in fixer
    assert "LIVRABLE" not in workshop._prompts("review", 0, "Faut-il acheter un NAS ?", [])[0]["content"]


def test_continuation_when_cut(client, monkeypatch):
    """Réponse coupée (finish_reason=length) : la suite est redemandée au même fournisseur et recollée."""
    import asyncio

    from app import providers

    p = providers.Provider("pc", "PC", "u", "k", "m", 100, "llama", 2, True)
    calls = []

    async def fake_stream(prov, messages, model=None, stats=None, max_tokens=None):
        calls.append((messages[-1]["content"][:30], max_tokens))
        part = "<html><body>début " if len(calls) == 1 else "fin</body></html>"
        stats.update(tokens=5, model="m", finish_reason="length" if len(calls) == 1 else "stop")
        yield part
    monkeypatch.setattr(providers, "stream", fake_stream)

    async def go():
        used = {}
        out = "".join([t async for t in providers.stream_complete([p], [{"role": "user", "content": "page"}], used, max_tokens=8000)])
        return out, used
    out, used = asyncio.run(go())
    assert out == "<html><body>début fin</body></html>" and used["continued"] == 1
    assert len(calls) == 2 and calls[1][0].startswith("Ta réponse a été coupée") and calls[1][1] == 8000


def test_architect_first_for_deliverables(client, monkeypatch):
    from app import workshop

    seen = []
    real_gen = workshop._gen

    async def spy(engine, messages, on_engine):
        seen.append(messages)
        async for t in real_gen(engine, messages, on_engine):
            yield t
    monkeypatch.setattr(workshop, "_gen", spy)
    msg = "Crée une page web pour mon entreprise de réparation de PC"
    pv = client.post("/api/workshop/preview", json={"message": msg, "pattern": "review"}).json()
    assert pv["architect_active"] and pv["steps"][0]["role"] == "Architecte" and pv["calls"] == 4
    off = client.post("/api/workshop/preview", json={"message": msg, "pattern": "review", "architect": "off"}).json()
    assert not off["architect_active"] and off["calls"] == 3
    assert not client.post("/api/workshop/preview", json={"message": "Faut-il un NAS ?"}).json()["architect_active"]
    with client.stream("POST", "/api/workshop/run", json={"message": msg, "pattern": "review"}) as r:
        events = [json.loads(line) for line in r.iter_lines() if line]
    plan = next(e for e in events if e["type"] == "plan")
    assert plan["steps"][0]["role"] == "Architecte" and len(plan["steps"]) == 4
    starts = [e for e in events if e["type"] == "step" and e["status"] == "start"]
    assert [e["index"] for e in starts] == list(range(len(starts))) and starts[0]["role"] == "Architecte"
    assert "ARCHITECTE" in seen[0][0]["content"]
    assert "Cahier des charges établi par l'architecte" in seen[1][1]["content"]      # le rédacteur part du cahier


def test_rounds_hint(client):
    r = client.post("/api/workshop/preview", json={"pattern": "review", "rounds": 3}).json()
    assert any("3 tours" in w for w in r["warnings"])


def test_retry_remote_before_local(client, monkeypatch):
    """Tous les fournisseurs en pause pour quelques secondes : l'atelier attend et réessaie au lieu de passer au local."""
    import asyncio

    from app import providers, workshop

    calls = {"n": 0}

    async def fake_complete(order, messages, used, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise providers.Unavailable("limite de l'offre atteinte pour le moment")
        used.update(id="mistral")
        yield "réponse distante"
    slept = []

    async def fast_sleep(s):
        slept.append(s)
    monkeypatch.setattr(providers, "stream_complete", fake_complete)
    monkeypatch.setattr(providers, "soonest_resume", lambda sensitive=False: 12.0)
    monkeypatch.setattr(workshop.asyncio, "sleep", fast_sleep)
    switched = []

    async def go():
        return "".join([t async for t in workshop._gen("p:mistral", [{"role": "user", "content": "x"}],
                                                        lambda e, why: switched.append(e))])
    assert asyncio.run(go()) == "réponse distante"
    assert calls["n"] == 2 and slept == [13.0] and "local" not in switched


def test_chat_gets_deliverable_rules(client, monkeypatch):
    from app import llm

    seen = []
    real = llm.stream_chat

    async def spy(model, messages, task=None):
        seen.append(messages[0]["content"])
        async for t in real(model, messages, task=task):
            yield t
    monkeypatch.setattr(llm, "stream_chat", spy)
    from conftest import chat
    chat(client, "Crée une page web html pour ma boulangerie")
    assert "Livrable demandé" in seen[-1]
    chat(client, "Quelle heure est-il ?")
    assert "Livrable demandé" not in seen[-1]
