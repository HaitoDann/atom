import asyncio
import io
import zipfile

import httpx
import pytest

from app import library, search


def test_sibling_project_not_readable(client):
    a = library.create_collection("p1", "code", "https://github.com/x/p1")
    b = library.create_collection("p1b", "code", "https://github.com/x/p1b")
    ra, rb = library.REPOS_DIR / str(a), library.REPOS_DIR / str(b)
    ra.mkdir(parents=True, exist_ok=True); rb.mkdir(parents=True, exist_ok=True)
    (rb / "secret.txt").write_text("secret")
    # chemin qui sort du projet a vers un projet voisin au nom qui commence pareil
    rel = f"../{rb.name}/secret.txt"
    with pytest.raises(FileNotFoundError):
        library.read_file(a, rel)


def test_private_addresses_refused():
    assert not search._public_host("127.0.0.1")
    assert not search._public_host("192.168.1.28")
    assert not search._public_host("10.0.0.5")
    assert not search._public_host("localhost")
    req = httpx.Request("GET", "http://192.168.1.1/admin")
    with pytest.raises(httpx.RequestError):
        asyncio.run(search._check_request(req))


def test_zip_bomb_refused():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", "0" * (41 * 1024 * 1024))
    with pytest.raises(library.Unsupported):
        library.extract_pages("a.docx", buf.getvalue())


def test_switch_unknown_branch(client):
    import subprocess
    cid = library.create_collection("g", "code", "https://github.com/x/g")
    root = library.REPOS_DIR / str(cid)
    root.mkdir(parents=True, exist_ok=True)
    (root / "a").write_text("a")
    for cmd in (["init", "-q", "-b", "main"], ["add", "."], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"]):
        subprocess.run(["git", "-C", str(root), *cmd], check=True)
    r = client.post(f"/api/git/{cid}/switch", json={"name": "--orphan=evil"})
    assert r.status_code == 409


def test_csrf_and_auth(client):
    assert client.post("/api/spaces", json={"name": "x"}, headers={"X-Atom": "0"}).status_code == 403
    from fastapi.testclient import TestClient
    import app.main as m
    anon = TestClient(m.app)
    assert anon.get("/api/conversations").status_code == 401
    assert anon.get("/api/analysis/abc").status_code == 401
