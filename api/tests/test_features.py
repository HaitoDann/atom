import json


def test_canvas(client):
    c = client.post("/api/canvas", json={"title": "Lettre", "content": "Bonjour Paul,\nMerci pour hier."}).json()
    r = client.post(f"/api/canvas/{c['id']}/edit", json={"instruction": "plus formel", "selection": "Merci pour hier."}).json()
    assert r["content"].startswith("Bonjour Paul,") and len(r["versions"]) == 2
    old = client.get(f"/api/canvas/{c['id']}/versions/0").json()["content"]
    assert old.endswith("Merci pour hier.")
    r = client.put(f"/api/canvas/{c['id']}", json={"content": "v3", "title": "Lettre 2"}).json()
    assert r["title"] == "Lettre 2" and r["versions"][-1]["by"] == "toi"
    assert any(x["id"] == c["id"] for x in client.get("/api/canvas").json()["canvases"])


def test_research(client, monkeypatch):
    from app import search

    async def fake_search(q):
        return [{"title": "Page A", "url": "https://a.example/x", "domain": "a.example", "snippet": "La RTX 3060 a 12 Go.", "content": "La RTX 3060 a 12 Go de mémoire."}]

    monkeypatch.setattr(search, "enabled", lambda: True)
    monkeypatch.setattr(search, "search", fake_search)
    lines = [json.loads(l) for l in client.post("/api/research", json={"message": "Combien de mémoire a la RTX 3060 ?"}).text.splitlines()]
    kinds = [l["type"] for l in lines]
    assert kinds[0] == "meta" and "progress" in kinds and kinds[-1] == "done"
    conv = lines[0]["conversation_id"]
    msgs = client.get(f"/api/conversations/{conv}/messages").json()["messages"]
    assert msgs[-1]["meta"]["sources"][0]["url"] == "https://a.example/x"


def test_rules(client):
    assert client.put("/api/agent/1/rules", json={"rules": ["Utiliser des tabulations", " "]}).json()["rules"] == ["Utiliser des tabulations"]
    assert client.get("/api/agent/1/rules").json()["rules"] == ["Utiliser des tabulations"]


def test_analyze_needs_sandbox(client):
    lines = [json.loads(l) for l in client.post("/api/analyze", json={"name": "a.csv", "data": "YSxiCjEsMgo=", "question": "?"}).text.splitlines()]
    assert lines[-1]["type"] == "error" and "bac à sable" in lines[-1]["message"]


def test_analyze_flow(client, monkeypatch):
    from app import sandbox
    calls = []

    async def fake_py(files, code, timeout=180):
        calls.append(code)
        if code.lstrip().startswith("import pandas as pd, sys, json"):
            return 0, "Dimensions : (3, 2)\nColonnes et types :\nmois object\nventes int64", {}
        if len(calls) == 2:
            return 1, "NameError: x", {}
        return 0, "Total des ventes : 42", {"graphique1.png": b"\x89PNG fake"}

    monkeypatch.setattr(sandbox, "enabled", lambda: True)
    monkeypatch.setattr(sandbox, "run_python", fake_py)
    lines = [json.loads(l) for l in client.post("/api/analyze", json={"name": "ventes.csv", "data": "YSxiCjEsMgo=", "question": "Total ?"}).text.splitlines()]
    assert lines[-1]["type"] == "done" and len(calls) == 3          # aperçu, échec, correction réussie
    conv = lines[0]["conversation_id"]
    meta = client.get(f"/api/conversations/{conv}/messages").json()["messages"][-1]["meta"]["analysis"]
    assert meta["ok"] and len(meta["images"]) == 1
    assert client.get(f"/api/analysis/{meta['images'][0]}").content == b"\x89PNG fake"
    assert client.get("/api/analysis/..%2Fatom.db").status_code == 404
