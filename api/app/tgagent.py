"""Agent de code depuis Telegram.

  /agent                       → liste des projets
  /agent leyo ajoute des tests pour Parse
                               → lance l'agent (sur le serveur), suit sa progression dans un message,
                                 puis envoie le résumé et les fichiers modifiés avec des boutons :
                                 [Voir le diff] [Appliquer] [Abandonner] — puis [Commit] et [Pousser].
  Répondre au message de résultat = « Poursuivre » (l'agent garde le contexte et les modifications).
Les actions passent par les mêmes garde-fous que l'interface : jamais de push sur la branche principale,
jamais de force-push, rien n'est écrit sans un clic.
"""

from __future__ import annotations

import asyncio
import html
import re
import time

from . import agentcode, db, gitops, library

STEP_LABEL = {"list": "liste", "read": "lit", "search": "cherche", "edit": "modifie", "write": "écrit", "test": "teste"}


def _projects() -> list[dict]:
    return [c for c in library.list_collections() if c["kind"] == "code"]


def find_project(name: str) -> dict | None:
    n = name.lower()
    ps = _projects()
    return (next((p for p in ps if p["name"].lower() == n), None)
            or next((p for p in ps if p["name"].lower().startswith(n)), None)
            or next((p for p in ps if n in p["name"].lower().replace(" ", "").replace("_", "")), None))


def _kb(rows: list[list[tuple[str, str]]]) -> dict:
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in rows]}


def _result_kb(rid: str, run: dict) -> dict | None:
    files = run.get("files") or {}
    if not files:
        return None
    col = library.get_collection(run["collection_id"])
    from .codeedit import writable
    rows = [[("📄 Voir le diff", f"ag:diff:{rid}")]]
    rows.append(([("✅ Appliquer", f"ag:apply:{rid}")] if col and writable(col) else []) + [("🗑 Abandonner", f"ag:drop:{rid}")])
    return _kb(rows)


async def start(tg, client, chat_id: int, args: str, parent: str | None = None) -> None:
    """tg : module telegram (send_text, edit_text, call)."""
    if parent:
        run = agentcode.get_run(parent)
        if not run:
            await tg.send_text(client, chat_id, "Cette tâche n'existe plus.")
            return
        col, task = library.get_collection(run["collection_id"]), args
    else:
        parts = args.split(maxsplit=1)
        if not parts:
            ps = _projects()
            await tg.send_text(client, chat_id, ("**Projets de code**\n\n" + "\n".join(f"• {p['name']}" for p in ps) +
                                                 "\n\nUsage : `/agent nom-du-projet ta demande`") if ps else "Aucun projet de code dans la bibliothèque.")
            return
        col = find_project(parts[0])
        if not col:
            await tg.send_text(client, chat_id, f"Projet « {parts[0]} » introuvable. /agent pour la liste.")
            return
        task = parts[1] if len(parts) > 1 else ""
    if len(task.strip()) < 3:
        await tg.send_text(client, chat_id, "Dis-moi ce que l'agent doit faire, ex. `/agent " + col["name"] + " explique l'architecture`")
        return
    rid = agentcode.start(col["id"], task, "remote", parent)
    msg = await tg.send_text(client, chat_id, f"🛠 **Agent** · {col['name']}\n_{task[:200]}_\n\nDémarrage…")
    asyncio.create_task(_follow(tg, client, chat_id, msg["message_id"] if msg else None, rid, col["name"], task))


async def _follow(tg, client, chat_id: int, mid: int | None, rid: str, name: str, task: str) -> None:
    last, shown, t0 = "", 0, time.time()
    while True:
        await asyncio.sleep(3)
        run = agentcode.get_run(rid)
        if not run:
            return
        evs = run["events"]
        steps = [e for e in evs if e["type"] == "action" and e["tool"] != "done"]
        if run["status"] == "running":
            line = ""
            if steps:
                s = steps[-1]
                line = f"{STEP_LABEL.get(s['tool'], s['tool'])} {s['args'].get('path') or s['args'].get('query') or s['args'].get('dir') or ''}".strip()
            text = f"🛠 **Agent** · {name}\n_{task[:200]}_\n\n{len(steps)} étape(s) · {int(time.time() - t0)} s\n→ {line or 'réfléchit…'}"
            if mid and text != last and time.time() - shown > 5:
                await tg.edit_text(client, chat_id, mid, text, formatted=True)
                last, shown = text, time.time()
            if time.time() - t0 > 30 * 60:
                return
            continue
        done = next((e for e in reversed(evs) if e["type"] == "done"), {})
        errors = [e["message"] for e in evs if e["type"] == "error"]
        files = done.get("files") or []
        head = {"done": "✅ Terminé", "stopped": "⏹ Arrêté", "error": "⚠ Interrompu", "interrupted": "⚠ Interrompu"}.get(run["status"], run["status"])
        body = f"**{head}** · {name} · {len(steps)} étape(s)\n\n"
        if done.get("summary"):
            body += done["summary"][:3000] + "\n\n"
        if errors:
            body += "Erreur : " + errors[-1][:300] + "\n\n"
        if files:
            body += "**Fichiers modifiés** (rien n'est encore écrit) :\n" + "\n".join(
                f"• `{f['path']}` +{f['added']} −{f['removed']}" + (" (nouveau)" if f.get("new_file") else "") for f in files)
            body += "\n\n_Réponds à ce message pour poursuivre la tâche._"
        else:
            body += "_Réponds à ce message pour poursuivre._"
        if mid:
            await tg.call(client, "deleteMessage", chat_id=chat_id, message_id=mid)
        kb = _result_kb(rid, run)
        res = await tg.send_text(client, chat_id, body, **({"reply_markup": kb} if kb else {}))
        if res:
            db.kv_set(f"tg_agent:{chat_id}:{res['message_id']}", rid)
        return


def run_for_reply(chat_id: int, reply_to: dict | None) -> str | None:
    if not reply_to:
        return None
    return db.kv_get(f"tg_agent:{chat_id}:{reply_to.get('message_id')}") or None


def _esc(t: str) -> str:
    return html.escape(t, quote=False)


async def on_button(tg, client, cq: dict) -> None:
    data = cq.get("data") or ""
    chat_id = cq["message"]["chat"]["id"]
    m = re.fullmatch(r"ag:(diff|apply|drop|commit|push):([0-9a-f]{16}|\d+)", data)
    await tg.call(client, "answerCallbackQuery", callback_query_id=cq["id"])
    if not m:
        return
    action, ref = m.groups()
    if action in ("commit", "push"):
        cid = int(ref)
        try:
            if action == "commit":
                st = gitops.status(cid)
                paths = [f["path"] for f in st["files"]]
                if not paths:
                    await tg.send_text(client, chat_id, "Rien à commiter.")
                    return
                if st["protected"]:
                    gitops.new_branch(cid, "atom/" + time.strftime("%Y%m%d-%H%M"))
                msg = await gitops.suggest_message(cid, paths)
                st = gitops.commit(cid, msg, paths)
                kb = _kb([[("⬆ Pousser sur GitHub", f"ag:push:{cid}")]]) if not st["protected"] else None
                await tg.send_text(client, chat_id, f"✅ Commit `{st['last']['hash']}` sur `{st['branch']}`\n\n{msg}", **({"reply_markup": kb} if kb else {}))
            else:
                st = gitops.push(cid)
                link = f"\n\n[Ouvrir une pull request]({st['compare']})" if st.get("compare") else ""
                await tg.send_text(client, chat_id, f"⬆ Branche `{st['pushed']}` poussée sur GitHub.{link}")
        except Exception as e:  # noqa: BLE001
            await tg.send_text(client, chat_id, f"Git : {e}")
        return
    rid = ref
    run = agentcode.get_run(rid)
    if not run:
        await tg.send_text(client, chat_id, "Cette tâche n'existe plus.")
        return
    done = next((e for e in reversed(run["events"]) if e["type"] == "done"), {})
    if action == "diff":
        diffs = [f for f in (done.get("files") or []) if f["path"] in (run.get("files") or {})]
        if not diffs:
            await tg.send_text(client, chat_id, "Plus aucun changement en attente.")
            return
        for f in diffs:
            d = f["diff"]
            for i in range(0, min(len(d), 12000), 3500):   # messages Telegram : 4096 caractères au plus
                await tg.call(client, "sendMessage", chat_id=chat_id, parse_mode="HTML",
                              text=f"<b>{_esc(f['path'])}</b>{' (suite)' if i else ''}\n<pre>{_esc(d[i:i + 3500])}</pre>")
            if len(d) > 12000:
                await tg.send_text(client, chat_id, "_(diff tronqué : voir l'interface web pour la totalité)_")
    elif action == "apply":
        try:
            r = agentcode.apply(rid, list((run.get("files") or {}).keys()))
        except Exception as e:  # noqa: BLE001
            await tg.send_text(client, chat_id, f"Application impossible : {e}")
            return
        from . import library as lib
        asyncio.create_task(lib.index_project(r["collection_id"]))
        txt = f"✅ {len(r['applied'])} fichier(s) appliqué(s)."
        if r["conflicts"]:
            txt += f"\n⚠ En conflit (modifiés entre-temps) : {', '.join(r['conflicts'])}"
        await tg.send_text(client, chat_id, txt, reply_markup=_kb([[("📝 Commit", f"ag:commit:{r['collection_id']}")]]))
    elif action == "drop":
        agentcode.delete_run(rid)
        await tg.send_text(client, chat_id, "🗑 Modifications abandonnées.")
