import time


def test_backup_export_import_restore(client):
    b = client.post("/api/backups").json()
    names = [x["name"] for x in client.get("/api/backups").json()["backups"]]
    assert b["name"] in names
    exp = client.get("/api/export")
    assert exp.status_code == 200 and exp.content.startswith(b"SQLite format 3")
    assert client.post("/api/import", content=b"pas une base").status_code == 400
    r = client.post("/api/import", content=exp.content, headers={"Content-Type": "application/octet-stream"})
    assert r.status_code == 200 and r.json()["previous"].endswith("prerestore.db")
    # la session reste valide après restauration ? (la base restaurée contient la session de l'export)
    assert client.get("/api/conversations").status_code == 200


def test_library_upload_and_retrieve(client):
    cid = [c for c in client.get("/api/library").json()["collections"] if c["kind"] == "docs"][0]["id"]
    text = "Le préavis du bail est de trois mois pour le locataire."
    r = client.post(f"/api/library/collections/{cid}/documents", params={"name": "bail.txt"}, content=text.encode())
    assert r.status_code == 200
    did = r.json()["id"]
    for _ in range(50):
        d = client.get(f"/api/library/documents/{did}").json()
        if d["document"]["status"] != "indexing":
            break
        time.sleep(0.1)
    assert d["document"]["status"] == "ready" and d["chunks"]
    import asyncio
    from app import library
    hits = asyncio.run(library.retrieve(d["chunks"][0]["text"], [cid]))   # embeddings de test : texte identique
    assert hits and hits[0]["document_id"] == did


def test_code_project_and_path_safety(client, tmpdir_root):
    proj = tmpdir_root / "projects" / "demo"
    (proj / "src").mkdir(parents=True, exist_ok=True)
    (proj / "src" / "main.py").write_text("def hello():\n    return 'monde'\n")
    (proj / "node_modules").mkdir(exist_ok=True)
    (proj / "node_modules" / "x.js").write_text("ignored()")
    assert client.post("/api/library/collections", json={"name": "x", "kind": "code", "source": "../../etc"}).status_code == 400
    c = client.post("/api/library/collections", json={"name": "Demo", "kind": "code", "source": "demo"}).json()
    for _ in range(50):
        col = [x for x in client.get("/api/library").json()["collections"] if x["id"] == c["id"]][0]
        if col["status"] != "indexing":
            break
        time.sleep(0.1)
    docs = client.get(f"/api/library/collections/{c['id']}/documents").json()["documents"]
    assert [d["path"] for d in docs] == ["src/main.py"]
    assert "monde" in client.get(f"/api/library/collections/{c['id']}/file", params={"path": "src/main.py"}).json()["content"]
    assert client.get(f"/api/library/collections/{c['id']}/file", params={"path": "../../../etc/passwd"}).status_code == 404
    g = client.get(f"/api/library/collections/{c['id']}/grep", params={"q": "hello"}).json()["matches"]
    assert g and g[0]["line"] == 1


def test_status_report(client):
    r = client.get("/api/status").json()
    assert r["status"] in ("ok", "warn", "error") and any(c["name"] == "Sauvegarde" for c in r["checks"])
