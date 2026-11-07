"""Analyse de données (comme « Code Interpreter ») : un CSV ou un Excel, une question → Python dans le bac à sable.

1. aperçu du fichier (colonnes, types, premières lignes) calculé dans le bac à sable ;
2. le modèle écrit un script pandas / matplotlib ;
3. exécution sans réseau ; en cas d'erreur, une correction automatique (2 essais au plus) ;
4. le modèle explique les résultats en français, graphiques à l'appui.
Le fichier ne quitte pas le serveur ; seuls l'aperçu et les résultats chiffrés sont envoyés au modèle
(distant uniquement si « bibliothèque et fichiers » est autorisé, et vers un fournisseur « private »).
"""

from __future__ import annotations

import base64
import re
import secrets
from pathlib import Path
from typing import AsyncIterator

from . import db, hybrid, llm, sandbox
from .config import DATA_DIR, DEFAULT_MODEL
import logging

log = logging.getLogger("atom.analysis")

OUT_DIR = DATA_DIR / "analysis"
DATA_EXT = {"csv", "tsv", "xlsx", "xls", "json", "parquet"}

PREVIEW = r'''
import pandas as pd, sys, json
p = "data/{name}"
ext = p.rsplit(".", 1)[-1].lower()
if ext in ("xlsx", "xls"):
    sheets = pd.read_excel(p, sheet_name=None)
    print("Feuilles :", list(sheets))
    df = next(iter(sheets.values()))
elif ext == "json":
    df = pd.read_json(p)
elif ext == "parquet":
    df = pd.read_parquet(p)
else:
    df = pd.read_csv(p, sep=None, engine="python")
print("Dimensions :", df.shape)
print("Colonnes et types :")
print(df.dtypes.to_string())
pd.set_option("display.width", 200); pd.set_option("display.max_columns", 30)
print("Premières lignes :")
print(df.head(5).to_string())
'''


def is_data(name: str) -> bool:
    return name.rsplit(".", 1)[-1].lower() in DATA_EXT if "." in name else False


async def _ask(messages: list[dict]) -> str:
    s = hybrid.settings()
    if hybrid.configured() and s.get("allow_docs"):
        try:
            return "".join([t async for t in hybrid.stream(messages, sensitive=True)])
        except Exception:  # noqa: BLE001
            log.warning("analysis : erreur gérée", exc_info=True)
            pass
    return "".join([t async for t in llm.stream_chat(db.kv_get("model") or DEFAULT_MODEL, messages)])


def _code(reply: str) -> str:
    m = re.search(r"```(?:python|py)?\s*\n([\s\S]*?)```", reply)
    return (m.group(1) if m else reply).strip()


SYS = ("Tu es un analyste de données qui écrit du Python (pandas, matplotlib). Réponds en français. "
       "Pas d'émotion entre crochets. /no_think")


async def run(name: str, raw: bytes, question: str, conversation_id: int | None) -> AsyncIterator[dict]:
    from .agent import make_title

    if not sandbox.enabled():
        yield dict(type="error", message="L'analyse de données a besoin du bac à sable (README → « Bac à sable »).")
        return
    if conversation_id is None or not db.conversation_exists(conversation_id):
        conversation_id = db.create_conversation("Analyse · " + make_title(question or name))
    yield dict(type="meta", conversation_id=conversation_id)
    user_id = db.add_message(conversation_id, "user", question or f"Analyse {name}", meta={"attachments": [{"name": name, "text": ""}], "analysis_file": name})
    yield dict(type="ids", user_id=user_id)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name)[-80:] or "donnees.csv"
    files = {f"data/{safe}": raw}

    yield dict(type="progress", text="Lecture du fichier dans le bac à sable…")
    code_, preview, _ = await sandbox.run_python(files, PREVIEW.replace("{name}", safe))
    if code_ != 0:
        msg = "Je n'arrive pas à lire ce fichier :\n```\n" + preview[-1500:] + "\n```"
        asst = db.add_message(conversation_id, "assistant", msg, "sad")
        yield dict(type="token", text=msg)
        yield dict(type="done", id=asst)
        return
    yield dict(type="progress", text="Aperçu : " + (re.search(r"Dimensions : \((\d+), (\d+)\)", preview) and
                                                      "{} lignes × {} colonnes".format(*re.search(r"Dimensions : \((\d+), (\d+)\)", preview).groups()) or "lu"))
    task = question.strip() or "Fais une analyse exploratoire utile : chiffres clés, tendances, anomalies, avec 1 ou 2 graphiques."
    messages = [{"role": "system", "content": SYS}, {"role": "user", "content":
        f"Fichier : data/{safe}\nAperçu :\n{preview[:4000]}\n\nQuestion : {task}\n\n"
        "Écris UN script Python complet qui répond à la question :\n"
        "- lis le fichier comme dans l'aperçu (pd.read_csv(..., sep=None, engine='python') pour un CSV) ;\n"
        "- affiche avec print() des résultats clairs et chiffrés (tableaux .to_string(), arrondis) ;\n"
        "- pour un graphique : matplotlib, titres et axes en français, plt.tight_layout(), "
        "plt.savefig('out/graphique1.png', dpi=110), puis plt.close() (2 graphiques au plus) ;\n"
        "- pas de réseau, pas de saisie, pas d'affichage interactif.\n"
        "Réponds uniquement avec le script dans un bloc ```python```."}]
    script, out, images, ok = "", "", {}, False
    for attempt in range(3):
        yield dict(type="progress", text="Écriture du script d'analyse…" if attempt == 0 else f"Correction du script (essai {attempt + 1})…")
        reply = await _ask(messages)
        script = _code(reply)
        yield dict(type="progress", text="Exécution sans réseau…", code=script)
        code_, out, images = await sandbox.run_python(files, script)
        if code_ == 0:
            ok = True
            break
        messages += [{"role": "assistant", "content": reply},
                     {"role": "user", "content": f"Le script a échoué (code {code_}) :\n{out[-2500:]}\nCorrige-le. Réponds uniquement avec le script complet dans un bloc ```python```."}]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    saved = []
    for fname, data in list(images.items())[:4]:
        if not fname.lower().endswith((".png", ".jpg", ".jpeg", ".svg")):
            continue
        fid = f"{secrets.token_hex(6)}_{re.sub(r'[^A-Za-z0-9._-]+', '_', fname)}"
        (OUT_DIR / fid).write_bytes(data)
        saved.append(fid)
    if saved:
        yield dict(type="progress", text=f"{len(saved)} graphique(s) produit(s)")

    yield dict(type="progress", text="Interprétation des résultats…")
    final_msgs = [{"role": "system", "content": SYS}, {"role": "user", "content":
        f"Question : {task}\n\nRésultats du script (sortie) :\n{out[-6000:]}\n\n" +
        (f"{len(saved)} graphique(s) ont été produits et seront affichés sous ta réponse.\n" if saved else "") +
        ("Le script a échoué malgré les corrections : explique simplement le problème et ce qu'il faudrait changer."
         if not ok else
         "Explique les résultats en français : commence par la réponse directe, puis les chiffres clés (tableau Markdown "
         "si utile), puis les points notables ou limites des données. N'invente aucun chiffre absent de la sortie.")}]
    text = ""
    s = hybrid.settings()
    if hybrid.configured() and s.get("allow_docs"):
        try:
            async for t in hybrid.stream(final_msgs, sensitive=True):
                text += t
                yield dict(type="token", text=t)
        except Exception:  # noqa: BLE001
            log.warning("analysis : erreur gérée", exc_info=True)
            text = ""
    if not text:
        async for t in llm.stream_chat(db.kv_get("model") or DEFAULT_MODEL, final_msgs):
            text += t
            yield dict(type="token", text=t)
    text = re.sub(r"^\s*\[[a-z_]+\]\s*", "", text).strip() or "…"
    meta = {"analysis": {"file": name, "code": script, "output": out[-4000:], "images": saved, "ok": ok}}
    asst = db.add_message(conversation_id, "assistant", text, "focus" if ok else "thinking", meta=meta)
    yield dict(type="done", id=asst)


def decode(data: str) -> bytes:
    return base64.b64decode(data, validate=False)


def image_path(fid: str) -> Path | None:
    if not re.fullmatch(r"[0-9a-f]{12}_[A-Za-z0-9._-]+", fid):
        return None
    p = OUT_DIR / fid
    return p if p.is_file() else None
