import asyncio
import subprocess

from app import library, tgagent


class FakeTG:
    def __init__(self):
        self.sent, self.calls, self.n = [], [], 100

    async def send_text(self, client, chat_id, text, **extra):
        self.n += 1
        self.sent.append((text, extra))
        return {"message_id": self.n}

    async def edit_text(self, client, chat_id, mid, text, formatted=True):
        pass

    async def call(self, client, method, **kw):
        self.calls.append((method, kw))
        return {}


def test_telegram_agent_flow(client, monkeypatch):
    cid = library.create_collection("tgdemo", "code", "https://github.com/x/tgdemo")
    root = library.REPOS_DIR / str(cid)
    root.mkdir(parents=True, exist_ok=True)
    (root / "app.py").write_text("print('x')\n")
    for cmd in (["init", "-q", "-b", "main"], ["add", "."], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"]):
        subprocess.run(["git", "-C", str(root), *cmd], check=True)
    with library.db.conn() as c:
        c.execute("INSERT INTO documents (collection_id, name, path, size, chars, hash, status, created_at) VALUES (?, 'app.py', 'app.py', 1, 1, 'x', 'ready', 0)", (cid,))
    assert tgagent.find_project("tgde")["id"] == cid

    async def fast_sleep(s):
        await asyncio.sleep(0)

    tg = FakeTG()

    async def go():
        real = asyncio.sleep
        monkeypatch.setattr(tgagent.asyncio, "sleep", lambda s: real(0.05))
        await tgagent.start(tg, None, 1, "tgdemo ajoute un commentaire")
        for _ in range(200):
            await real(0.05)
            if any("Terminé" in t for t, _ in tg.sent):
                break

    asyncio.run(go())
    res = next((t, e) for t, e in tg.sent if "Terminé" in t)
    assert "app.py" in res[0] and res[1]["reply_markup"]["inline_keyboard"]
    rid = res[1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"].split(":")[2]
    assert tgagent.run_for_reply(1, {"message_id": tg.n}) == rid
    asyncio.run(tgagent.on_button(tg, None, {"id": "q", "data": f"ag:apply:{rid}", "message": {"chat": {"id": 1}}}))
    assert (root / "app.py").read_text().startswith("# modifié par l'agent")
    asyncio.run(tgagent.on_button(tg, None, {"id": "q", "data": f"ag:commit:{cid}", "message": {"chat": {"id": 1}}}))
    assert any("Commit" in t and "atom/" in t for t, _ in tg.sent)     # branche atom/… créée (pas de commit sur main)
