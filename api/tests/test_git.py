import subprocess

from app import library


def _repo(name):
    cid = library.create_collection(name, "code", f"https://github.com/exemple/{name}")
    root = library.REPOS_DIR / str(cid)
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.py").write_text("x = 1\n")
    for cmd in (["init", "-q", "-b", "main"], ["add", "."], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"]):
        subprocess.run(["git", "-C", str(root), *cmd], check=True)
    return cid, root


def test_git_flow(client):
    cid, root = _repo("gitdemo")
    st = client.get(f"/api/git/{cid}/status").json()
    assert st["branch"] == "main" and st["protected"] and st["files"] == []

    (root / "a.py").write_text("x = 2\n")
    (root / "b.py").write_text("y = 1\n")
    st = client.get(f"/api/git/{cid}/status").json()
    assert {f["path"] for f in st["files"]} == {"a.py", "b.py"}

    # pas de push sur la branche principale
    assert client.post(f"/api/git/{cid}/push").status_code == 403
    assert client.post(f"/api/git/{cid}/branch", json={"name": "../x"}).status_code == 409
    st = client.post(f"/api/git/{cid}/branch", json={"name": "atom/essai"}).json()
    assert st["branch"] == "atom/essai" and not st["protected"] and len(st["files"]) == 2

    msg = client.post(f"/api/git/{cid}/message", json={"paths": ["a.py"]}).json()["message"]
    assert "a.py" in msg
    st = client.post(f"/api/git/{cid}/commit", json={"message": msg, "paths": ["a.py"]}).json()
    assert [f["path"] for f in st["files"]] == ["b.py"] and st["ahead"] >= 1
    assert st["last"]["subject"] == msg

    st = client.post(f"/api/git/{cid}/discard").json()
    assert st["files"] == [] and not (root / "b.py").exists()
    assert client.post(f"/api/git/{cid}/switch", json={"name": "main"}).json()["branch"] == "main"
    assert (root / "a.py").read_text() == "x = 1\n"
