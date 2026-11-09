import subprocess

from app import library


def test_propose_apply_revert(client):
    cid = library.create_collection("demo", "code", "https://github.com/exemple/demo")
    root = library.REPOS_DIR / str(cid)
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.py").write_text("x = 1\ny = 2\n")
    for cmd in (["init", "-q"], ["add", "."], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"]):
        subprocess.run(["git", "-C", str(root), *cmd], check=True)

    r = client.post(f"/api/code/{cid}/propose", json={"path": "a.py", "instruction": "ajoute un commentaire", "start": 2, "end": 2})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["writable"] and "+# modifié par Atom" in p["diff"] and p["added"] == 1

    assert client.post(f"/api/code/proposals/{p['id']}/apply").status_code == 200
    assert (root / "a.py").read_text() == "x = 1\n# modifié par Atom\ny = 2\n"
    ch = client.get(f"/api/code/{cid}/changes").json()
    assert ch["files"] == [{"path": "a.py", "status": "modifié"}]

    assert client.post(f"/api/code/{cid}/revert", json={"path": "a.py"}).status_code == 200
    assert (root / "a.py").read_text() == "x = 1\ny = 2\n"
    assert client.post(f"/api/code/{cid}/propose", json={"path": "../etc/passwd", "instruction": "xx"}).status_code == 404


def test_project_from_files(client):
    """Les fichiers d'une réponse deviennent un projet modifiable du mode Code (dépôt Git local)."""
    import subprocess

    from app import library
    r = client.post("/api/projects/from-files", json={"name": "Boulangerie Lyon", "files": [
        {"path": "index.html", "content": "<h1>Pain</h1>"}, {"path": "css/style.css", "content": "h1{color:red}"}]})
    assert r.status_code == 200, r.text
    cid = r.json()["collection_id"]
    col = library.get_collection(cid)
    root = library._code_root(col)
    assert col["kind"] == "code" and col["source"].startswith("atom:")
    assert (root / "css/style.css").read_text() == "h1{color:red}"
    log = subprocess.run(["git", "-C", str(root), "log", "--oneline"], capture_output=True, text=True).stdout
    assert "Version générée par Atom" in log
    from app.codeedit import writable
    assert writable(col)
    for bad in ("../evil.sh", "/etc/passwd", ".git/config"):
        assert client.post("/api/projects/from-files", json={"name": "x", "files": [{"path": bad, "content": "x"}]}).status_code == 400
