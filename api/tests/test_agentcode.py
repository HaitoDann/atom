import json
import subprocess
import time

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


def _go(client, cid, **body):
    rid = client.post(f"/api/agent/{cid}", json=body).json()["id"]
    for _ in range(100):
        r = client.get(f"/api/agent/runs/{rid}").json()
        if r["status"] != "running":
            return rid, r["events"]
        time.sleep(0.05)
    raise AssertionError("agent trop long")


def test_agent_run_and_apply(client):
    cid, root = _project()
    rid, lines = _go(client, cid, task="ajoute un commentaire", engine="local")
    kinds = [l["type"] for l in lines]
    assert kinds[0] == "start" and "action" in kinds and kinds[-1] == "done"
    done = lines[-1]
    assert [f["path"] for f in done["files"]] == ["app.py"] and "+# modifié par l'agent" in done["files"][0]["diff"]
    assert (root / "app.py").read_text() == "print('hello')\n"        # rien d'écrit avant validation
    r = client.post(f"/api/agent/runs/{done['id']}/apply", json={"paths": ["app.py"]}).json()
    assert r["applied"] == ["app.py"] and (root / "app.py").read_text().startswith("# modifié par l'agent")
    # historique et relecture après « F5 »
    runs = client.get(f"/api/agent/{cid}/runs").json()["runs"]
    assert runs[0]["id"] == rid and runs[0]["status"] == "done"
    again = client.get(f"/api/agent/runs/{rid}?after=1").json()
    assert again["total"] == len(lines) and again["events"][-1]["applied"] == ["app.py"]
    # « Poursuivre » : nouvelle tâche liée à la précédente
    rid2, lines2 = _go(client, cid, task="continue", engine="local", parent=rid)
    assert client.get(f"/api/agent/runs/{rid2}").json()["parent"] == rid


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


def test_paths_normalized():
    cid, root = _project()
    ws = agentcode.Workspace(cid)
    assert "app.py" in ws.t_list("./") and "app.py" in ws.t_list(".") and "app.py" in ws.t_list("/")
    assert ws.t_read("./app.py").startswith("app.py")


def test_agent_native_tools(client):
    cid, root = _project()
    from app import hybrid
    hybrid.save_settings({"allow_docs": True})
    try:
        _, lines = _go(client, cid, task="commente", engine="remote")
    finally:
        hybrid.save_settings({"allow_docs": False})
    assert lines[0]["engine"] == "remote"
    assert [l["tool"] for l in lines if l["type"] == "action"] == ["list", "read", "edit", "done"]
    done = lines[-1]
    assert done["summary"].endswith("(outils natifs).") and done["files"][0]["path"] == "app.py"


def test_fit_budget():
    msgs = [{"role": "system", "content": "s" * 2000}, {"role": "user", "content": "Tâche"}]
    for i in range(6):
        msgs.append({"role": "assistant", "content": "x"})
        msgs.append({"role": "tool", "tool_call_id": str(i), "content": "ligne de code\n" * 600})
    small = agentcode._fit(msgs, 5000)
    assert agentcode._est(small) <= 5200 and len(msgs[-1]["content"]) > len(small[-1]["content"]) - 1
    assert msgs[3]["content"].count("\n") == 600     # l'original n'est pas modifié


def test_rate_limit_pause(client, monkeypatch):
    import asyncio as aio
    from app import hybrid, providers
    cid, root = _project()
    calls = {"n": 0}
    real = providers.chat_tools

    async def flaky(p, messages, tools, max_tokens=4096):
        calls["n"] += 1
        if calls["n"] == 1:
            raise providers.RateLimited("limite par minute de l'offre Test", 1)
        return await real(p, messages, tools, max_tokens)

    async def fast_sleep(s):
        return None

    monkeypatch.setattr(providers, "chat_tools", flaky)
    monkeypatch.setattr(aio, "sleep", fast_sleep)
    hybrid.save_settings({"allow_docs": True})
    try:
        _, lines = _go(client, cid, task="commente", engine="remote")
    finally:
        hybrid.save_settings({"allow_docs": False})
    assert any(l["type"] == "info" and "pause" in l["message"] for l in lines)
    assert lines[-1]["files"] and not any("en local" in l.get("message", "") for l in lines)


def test_validation_and_permissions():
    ro = {"read"}
    assert "non autorisé" in agentcode.validate("edit", {"path": "a.py", "old": "x", "new": "y"}, ro)
    assert agentcode.validate("read", {"path": "a.py", "start": 1}, ro) is None
    assert "numéro de ligne" in agentcode.validate("read", {"path": "a.py", "start": "1; rm"}, ro)
    assert "trop long" in agentcode.validate("search", {"query": "x" * 400}, ro)
    assert "texte" in agentcode.validate("read", {"path": ["a"]}, ro)
    names = [t["function"]["name"] for t in agentcode.tools({"read"})]
    assert "edit" not in names and "write" not in names and "read" in names


def test_readonly_run_makes_no_change(client):
    cid, root = _project()
    rid, lines = _go(client, cid, task="ajoute un commentaire", engine="local", readonly=True)
    done = lines[-1]
    assert done["files"] == [] and any(l["type"] == "result" and "non autorisé" in l["text"] for l in lines)
