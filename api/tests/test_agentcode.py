import json
import subprocess

from app import agentcode, library


def _project():
    cid = library.create_collection("agentdemo", "code", "https://github.com/exemple/agentdemo")
    root = library.REPOS_DIR / str(cid)
    root.mkdir(parents=True, exist_ok=True)
    (root / "app.py").write_text("print('hello')\n")
    for cmd in (["init", "-q"], ["add", "."], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"]):
        subprocess.run(["git", "-C", str(root), *cmd], check=True)
    with library.db.conn() as c:
        c.execute("INSERT INTO documents (collection_id, name, path, size, chars, hash, status, created_at) VALUES (?, 'app.py', 'app.py', 1, 1, 'x', 'ready', 0)", (cid,))
    return cid, root


def test_agent_run_and_apply(client):
    cid, root = _project()
    lines = [json.loads(l) for l in client.post(f"/api/agent/{cid}", json={"task": "ajoute un commentaire", "engine": "local"}).text.splitlines()]
    kinds = [l["type"] for l in lines]
    assert kinds[0] == "start" and "action" in kinds and kinds[-1] == "done"
    done = lines[-1]
    assert [f["path"] for f in done["files"]] == ["app.py"] and "+# modifié par l'agent" in done["files"][0]["diff"]
    assert (root / "app.py").read_text() == "print('hello')\n"        # rien d'écrit avant validation
    r = client.post(f"/api/agent/runs/{done['id']}/apply", json={"paths": ["app.py"]}).json()
    assert r["applied"] == ["app.py"] and (root / "app.py").read_text().startswith("# modifié par l'agent")


def test_workspace_guards():
    cid, root = _project()
    ws = agentcode.Workspace(cid)
    assert "Lis d'abord" in ws.t_edit("app.py", "print", "x")
    assert "hors du projet" in str(_err(lambda: ws.t_read("../../etc/passwd")))
    ws.t_read("app.py")
    assert "introuvable" in ws.t_edit("app.py", "absent", "x")
    assert ws.t_edit("app.py", "hello", "bonjour").startswith("OK")
    assert "bonjour" in ws.t_search("bonjour")
    assert ws.t_write("new/f.py", "x = 1").startswith("OK") and "new/" in ws.t_list("")
    assert {d["path"] for d in ws.diffs()} == {"app.py", "new/f.py"}


def _err(fn):
    try:
        fn()
    except ValueError as e:
        return e
    return None


def test_parse():
    t, a = agentcode._parse('Je lis.\n```action\n{"tool": "read", "path": "a.py"}\n```')
    assert t == "Je lis." and a == {"tool": "read", "path": "a.py"}
    assert agentcode._parse("pas d'action")[1] is None
