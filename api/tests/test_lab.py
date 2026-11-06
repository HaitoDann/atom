import json
import time


def test_lab(client):
    d = client.get("/api/lab").json()
    assert d["suggested"] and d["prompts"]
    assert client.post("/api/lab/install", json={"name": "rm -rf /"}).status_code == 422
    assert client.post("/api/lab/install", json={"name": "gemma3:4b"}).status_code == 200
    for _ in range(30):
        st = next(p for p in client.get("/api/lab").json()["pulls"] if p["name"] == "gemma3:4b")
        if st["done"]:
            break
        time.sleep(0.2)
    assert st["status"] == "terminé"
    lines = [json.loads(l) for l in client.post("/api/lab/compare", json={"models": ["a", "b"], "prompts": ["code"], "custom": "Salut"}).text.splitlines()]
    res = [l for l in lines if l["type"] == "result"]
    assert len(res) == 4 and {r["model"] for r in res} == {"a", "b"} and lines[-1]["type"] == "done"
    assert all(r["first_s"] is not None for r in res)
