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
