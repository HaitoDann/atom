"""Discussion : passage automatique ou suggéré à l'orchestration ; remplacement d'un modèle disparu."""

import asyncio
import json

import pytest

DIFFICILE = "Cherche les prix actuels, puis compare-les, ensuite rédige une synthèse et enfin vérifie les calculs"


def test_orchestration_plan_modes(client):
    from app import hybrid
    hybrid.save_settings({"orchestrate": "suggest"})
    p = hybrid.orchestration_plan(DIFFICILE)
    assert p["difficulty"] == "difficile" and p["suggest"] and not p["orchestrate"] and p["reason"]
    assert not hybrid.orchestration_plan("Bonjour !")["suggest"]                     # simple : en direct
    assert not hybrid.orchestration_plan(DIFFICILE, has_files=True)["suggest"]      # fichiers joints : discussion
    assert not hybrid.orchestration_plan(DIFFICILE, engine="mistral")["suggest"]    # modèle distant imposé
    hybrid.save_settings({"orchestrate": "auto"})
    assert hybrid.orchestration_plan(DIFFICILE)["orchestrate"]
    hybrid.save_settings({"orchestrate": "off"})
    assert not hybrid.orchestration_plan(DIFFICILE)["orchestrate"]
    hybrid.save_settings({"orchestrate": "n'importe quoi"})
    assert hybrid.settings()["orchestrate"] == "suggest"


def test_route_plan_endpoint_and_settings(client):
    r = client.put("/api/hybrid", json={"orchestrate": "auto", "auto_replace": False}).json()
    assert r["orchestrate"] == "auto" and r["auto_replace"] is False
    assert client.post("/api/route/plan", json={"message": DIFFICILE}).json()["orchestrate"] is True
    assert client.put("/api/hybrid", json={"orchestrate": "parfois"}).status_code == 422
    client.put("/api/hybrid", json={"orchestrate": "suggest", "auto_replace": True})


def test_chat_suggests_orchestration(client):
    from conftest import chat
    client.put("/api/hybrid", json={"orchestrate": "suggest", "mode": "local"})
    done = [e for e in chat(client, DIFFICILE) if e["type"] == "done"][0]
    assert "suggest_orchestra" in done
    done = [e for e in chat(client, "Salut") if e["type"] == "done"][0]
    assert "suggest_orchestra" not in done


@pytest.mark.parametrize("old,available,expected", [
    ("gemini-2.5-flash", ["gemini-2.0-flash", "gemini-3-flash", "gemini-3-pro", "gemini-3-flash-preview", "text-embedding-004",
                          "gemini-3-flash-image"], "gemini-3-flash"),
    ("llama-3.3-70b-versatile", ["llama-3.1-8b-instant", "llama-4-70b-versatile", "whisper-large-v3"], "llama-4-70b-versatile"),
    ("openai/gpt-4.1-mini", ["openai/gpt-5-mini", "openai/gpt-5", "meta/llama-4"], "openai/gpt-5-mini"),
    ("mistral-small-latest", ["gemma-3", "qwen3-32b"], None),                     # aucune même lignée : on ne devine pas
])
def test_pick_replacement(old, available, expected):
    from app import providers
    assert providers.pick_replacement(old, available) == expected


def test_replace_model_updates_setting_and_notifies(client, monkeypatch):
    from app import db, notify, providers
    p = providers.get("gemini") or providers.ALL[0]
    providers.set_model(p.id, "ancien-modele-1")
    sent = []

    async def lm(prov):
        return ["ancien-modele-2", "autre-chose"]

    async def fake_send(title, body, cid=None, tags="", buttons=None):
        sent.append((title, body))
        return True
    monkeypatch.setattr(providers, "list_models", lm)
    monkeypatch.setattr(notify, "send", fake_send)
    new = asyncio.run(providers.replace_model(p, "ancien-modele-1"))
    assert new == "ancien-modele-2" and providers.model_of(p) == "ancien-modele-2"
    assert sent and "ancien-modele-2" in sent[0][1]
    assert json.loads(db.kv_get("model_replacements"))[-1]["old"] == "ancien-modele-1"
    # déjà remplacé (le réglage ne correspond plus) : rien à faire
    assert asyncio.run(providers.replace_model(p, "ancien-modele-1")) is None
    # réglage désactivé : on ne touche à rien
    client.put("/api/hybrid", json={"auto_replace": False})
    providers.set_model(p.id, "x-1")
    monkeypatch.setattr(providers, "list_models", lambda prov: asyncio.sleep(0, ["x-2"]))
    assert asyncio.run(providers.replace_model(p, "x-1")) is None and providers.model_of(p) == "x-1"
    client.put("/api/hybrid", json={"auto_replace": True})
    providers.set_model(p.id, "")


def test_brief_reports_replacement(client, monkeypatch):
    from app import brief, providers

    class P:
        id, name, configured = "gem", "Gemini", True
    prov = P()
    monkeypatch.setattr(providers, "ALL", [prov])
    state = {"model": "gemini-old"}
    monkeypatch.setattr(providers, "model_of", lambda p: state["model"])

    async def ping(p):
        return "modèle introuvable" if state["model"] == "gemini-old" else ""

    async def replace(p, old):
        state["model"] = "gemini-new"
        return "gemini-new"
    monkeypatch.setattr(providers, "ping", ping)
    monkeypatch.setattr(providers, "replace_model", replace)
    out = asyncio.run(brief.section_providers())
    assert "Tous opérationnels" in out and "remplacé par « gemini-new »" in out
