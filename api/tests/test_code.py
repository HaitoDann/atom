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
