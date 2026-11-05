from conftest import chat


def test_chat_stream_and_history(client):
    evs = chat(client, "Bonjour Atom")
    types = [e["type"] for e in evs]
    assert types[0] == "meta" and "emotion" in types and "token" in types and types[-1] == "done"
    cid = evs[0]["conversation_id"]
    msgs = client.get(f"/api/conversations/{cid}/messages").json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert "Bonjour Atom" in msgs[1]["content"]


def test_reminder_command_is_hidden_and_scheduled(client):
    evs = chat(client, "Rappelle-moi de tester Atom")
    text = "".join(e["text"] for e in evs if e["type"] == "token")
    assert "[[" not in text
    created = [e for e in evs if e["type"] == "reminder" and e["action"] == "created"]
    assert created
    rem = client.get("/api/reminders").json()["reminders"]
    assert any(r["id"] == created[0]["id"] for r in rem)
    assert client.delete(f"/api/reminders/{created[0]['id']}").status_code == 200


def test_edit_truncate_and_search(client):
    evs = chat(client, "Message unique zorglub")
    cid = evs[0]["conversation_id"]
    found = client.get("/api/search", params={"q": "zorglub"}).json()["results"]
    assert any(r["id"] == cid for r in found)
    first = client.get(f"/api/conversations/{cid}/messages").json()["messages"][0]
    client.post(f"/api/conversations/{cid}/truncate", json={"from_id": first["id"]})
    assert client.get(f"/api/conversations/{cid}/messages").json()["messages"] == []


def test_hybrid_routing_and_privacy(client):
    from app import hybrid

    assert hybrid.decide("local", "salut", False, False)[0] == "local"
    assert hybrid.decide("mistral", "salut", False, False)[0] == "mistral"
    assert hybrid.decide("auto", "salut", False, False)[0] == "local"
    assert hybrid.decide("auto", "Analyse en détail les avantages et inconvénients", False, False)[0] == "mistral"
    # documents non autorisés → reste en local
    assert hybrid.decide("mistral", "lis ça", False, True)[0] == "local"
    evs = chat(client, "salut", engine="mistral")
    assert [e for e in evs if e["type"] == "done"][0]["provider"] == "mistral"


def test_workshop(client):
    import json

    client.put("/api/workshop", json={"enabled": True, "pattern": "panel", "participants": ["local", "local", "local"]})
    with client.stream("POST", "/api/workshop/run", json={"message": "NAS ou cloud ?"}) as r:
        evs = [json.loads(l) for l in r.iter_lines() if l]
    starts = [e for e in evs if e["type"] == "step" and e["status"] == "start"]
    assert [s["role"] for s in starts] == ["Proposition A", "Proposition B", "Arbitre"]
    assert evs[-1]["type"] == "done"
    client.put("/api/workshop", json={"enabled": False})
