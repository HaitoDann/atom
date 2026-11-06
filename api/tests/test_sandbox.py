import asyncio
import io
import json
import tarfile

import httpx

from app import library, sandbox


def _project(tmp_files):
    cid = library.create_collection("sbdemo", "code", "https://github.com/exemple/sbdemo")
    root = library.REPOS_DIR / str(cid)
    root.mkdir(parents=True, exist_ok=True)
    for k, v in tmp_files.items():
        (root / k).parent.mkdir(parents=True, exist_ok=True)
        (root / k).write_text(v)
    (root / ".git").mkdir(exist_ok=True)
    (root / ".git" / "config").write_text("secret")
    return cid


def test_detect_and_snapshot(client):
    cid = _project({"go.mod": "module x\n", "main.go": "package main\n", "node_modules/a.js": "x"})
    data, names = sandbox.snapshot(cid, {"main.go": "package main // modifié\n", "new_test.go": "package main\n"})
    assert sandbox.detect(names) == "go" and "go test" in sandbox.default_command(cid, names)
    with tarfile.open(fileobj=io.BytesIO(data)) as t:
        members = {m.name: m for m in t.getmembers()}
        assert "work/main.go" in members and "work/new_test.go" in members
        assert not any(".git" in n or "node_modules" in n for n in members)
        assert t.extractfile("work/main.go").read().decode().endswith("modifié\n")


def test_demux():
    frame = b"\x01\x00\x00\x00" + (5).to_bytes(4, "big") + b"hello" + b"\x02\x00\x00\x00" + (4).to_bytes(4, "big") + b" err"
    assert sandbox.demux(frame) == "hello err"


def test_run_with_fake_docker(client, monkeypatch, tmp_path):
    cid = _project({"go.mod": "module x\n"})
    calls = []

    def handler(req: httpx.Request):
        calls.append((req.method, req.url.path, req.url.params.get("path"), req.content[:0]))
        p = req.url.path
        if p.startswith("/images/") and p.endswith("/json"):
            return httpx.Response(200, json={})
        if p == "/containers/create":
            body = json.loads(req.content)
            calls.append(("network", body["HostConfig"]["NetworkMode"], body["HostConfig"]["CapDrop"]))
            return httpx.Response(201, json={"Id": "abc"})
        if p.endswith("/wait"):
            return httpx.Response(200, json={"StatusCode": 0})
        if p.endswith("/logs"):
            return httpx.Response(200, content=b"\x01\x00\x00\x00" + (2).to_bytes(4, "big") + b"ok")
        return httpx.Response(200 if req.method != "POST" else 204)

    sock = tmp_path / "docker.sock"; sock.write_text("")
    monkeypatch.setattr(sandbox, "ENABLED", True)
    monkeypatch.setattr(sandbox, "SOCKET", str(sock))
    monkeypatch.setattr(sandbox, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://docker"))

    async def go():
        return [ev async for ev in sandbox.run(cid)]

    evs = asyncio.run(go())
    res = evs[-1]
    assert res["type"] == "result" and res["code"] == 0 and res["output"] == "ok"
    nets = [c[1] for c in calls if c[0] == "network"]
    assert nets == ["bridge", "none"]        # dépendances avec réseau, tests sans
    assert all(c[2] == ["ALL"] for c in calls if c[0] == "network")
    assert sum(1 for c in calls if c[0] == "DELETE") == 2   # conteneurs supprimés
    text = asyncio.run(sandbox.run_text(cid, None, None))
    assert text.startswith("Tests réussis")


def test_disabled(client):
    cid = _project({"package.json": "{}"})
    info = client.get(f"/api/sandbox/{cid}").json()
    assert info["enabled"] is False and "ATOM_SANDBOX" in info["reason"]
