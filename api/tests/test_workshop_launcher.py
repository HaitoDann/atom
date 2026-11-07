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
