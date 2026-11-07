import json


def test_spaces_flow(client):
    sp = client.post("/api/spaces", json={"name": "Leyo", "instructions": "Réponds toujours en citant le fichier concerné."}).json()
    assert sp["name"] == "Leyo" and sp["collections"] == []
    lines = [json.loads(l) for l in client.post("/api/chat", json={"message": "Bonjour", "space_id": sp["id"]}).text.splitlines()]
    meta = next(l for l in lines if l["type"] == "meta")
    assert meta["space_id"] == sp["id"]
    convs = client.get("/api/conversations").json()["conversations"]
    assert any(c["id"] == meta["conversation_id"] and c["space_id"] == sp["id"] for c in convs)
    assert client.get("/api/spaces").json()["spaces"][0]["conversations"] == 1
    client.put(f"/api/conversations/{meta['conversation_id']}/space", json={"space_id": None})
    assert client.get("/api/spaces").json()["spaces"][0]["conversations"] == 0
    assert client.patch(f"/api/spaces/{sp['id']}", json={"instructions": "x"}).json()["instructions"] == "x"
    client.delete(f"/api/spaces/{sp['id']}")
    assert client.get("/api/spaces").json()["spaces"] == []
