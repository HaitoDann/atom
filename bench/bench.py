#!/usr/bin/env python3
"""Banc d'essai d'Atom : envoie les mêmes tâches à plusieurs méthodes, corrige les réponses et produit un rapport.

Méthodes :
  simple               discussion normale, moteur local (un seul appel)
  ask:<moteur>         un seul appel à un moteur précis (local, groq, gemini…), sans relais
  orchestra            orchestration vérifiée (exécutant : le local, ou le plus faible distant avec --no-local)
  orchestra:<moteur>   orchestration avec cet exécutant (ex. orchestra:groq)
  review[:<moteur>]    rédaction puis relecture (référence multi-IA classique)
--no-local : le modèle local n'intervient nulle part (aucun repli silencieux vers lui).
--list     : affiche les moteurs disponibles.

Usage (depuis le dossier atom, sur le serveur ou ton PC) :
  python3 bench/bench.py --url http://IP-DE-LA-VM:8000
  python3 bench/bench.py --methods simple,orchestra --only interets,jours --repeat 2
  python3 bench/bench.py --no-local --methods ask:groq,ask:gemini,orchestra:gemini
  python3 bench/bench.py --hard --no-local --methods ask:gemini,orchestra:gemini --judge groq --run-code

Aucune dépendance : bibliothèque standard de Python 3.9+.
Le mot de passe d'Atom est lu dans ATOM_BENCH_PASSWORD, sinon demandé au clavier (jamais écrit sur disque).
Résultats : bench/results/<date>/ → results.csv, rapport.md, answers/*.md, stats.json
"""

from __future__ import annotations

import argparse
import csv
import getpass
import http.cookiejar
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent


# ---------------------------------------------------------------- client HTTP

class Atom:
    def __init__(self, url: str, timeout: int):
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def _req(self, method: str, path: str, body: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, method=method,
                                     headers={"Content-Type": "application/json", "X-Atom": "1"})
        return self.opener.open(req, timeout=self.timeout)

    def json(self, method: str, path: str, body: dict | None = None):
        with self._req(method, path, body) as r:
            return json.loads(r.read() or b"{}")

    def login(self, password: str) -> None:
        try:
            self.json("POST", "/api/auth/login", {"password": password})
        except urllib.error.HTTPError as e:
            sys.exit(f"Connexion refusée ({e.code}) : {e.read().decode(errors='replace')[:200]}")

    def stream(self, path: str, body: dict) -> list[dict]:
        events = []
        with self._req("POST", path, body) as r:
            for line in r:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        return events


# ---------------------------------------------------------------- méthodes

def run_simple(atom: Atom, text: str) -> dict:
    ev = atom.stream("/api/chat", {"message": text, "engine": "local", "auto_memory": False, "web": "auto", "scope": "none"})
    answer = "".join(e.get("text", "") for e in ev if e.get("type") == "token")
    cid = next((e.get("conversation_id") for e in ev if e.get("type") == "meta"), None)
    err = next((e.get("message") for e in ev if e.get("type") == "error"), "")
    return {"answer": re.sub(r"^\s*\[[a-zA-Z]+\]\s*", "", answer), "cid": cid, "error": err, "steps": 1, "calls": 1}


def run_workshop(atom: Atom, text: str, pattern: str, participants: list[str] | None = None, allow_local: bool = True) -> dict:
    body = {"message": text, "pattern": pattern, "allow_local": allow_local}
    if participants:
        body["participants"] = participants
    ev = atom.stream("/api/workshop/run", body)
    done = next((e for e in ev if e.get("type") == "done"), None)
    cid = next((e.get("conversation_id") for e in ev if e.get("type") == "meta"), None)
    err = next((e.get("message") for e in ev if e.get("type") == "error"), "")
    starts = [e for e in ev if e.get("type") == "step" and e.get("status") == "start"]
    out = {"answer": (done or {}).get("final", ""), "cid": cid, "error": err, "steps": len(starts), "calls": len(starts)}
    if pattern == "orchestra" and cid:
        try:   # la trace détaillée est enregistrée avec la réponse
            msgs = atom.json("GET", f"/api/conversations/{cid}/messages")["messages"]
            info = (msgs[-1].get("meta") or {}).get("orchestra") or {}
            out["calls"] = info.get("calls", out["calls"])
            out["difficulty"] = info.get("difficulty", "")
            out["verified"] = ",".join(s.get("verified") or "?" for s in info.get("steps", []))
            out["escalated"] = sum(1 for s in info.get("steps", []) if s.get("escalated"))
            out["failures"] = ";".join(f["type"] for s in info.get("steps", []) for f in s.get("failures", []))
        except Exception:  # noqa: BLE001
            pass
    return out


def run_ask(atom: Atom, text: str, engine: str) -> dict:
    try:
        r = atom.json("POST", "/api/bench/ask", {"message": text, "engine": engine})
    except urllib.error.HTTPError as e:
        return {"answer": "", "cid": None, "error": f"{e.code} {e.read().decode(errors='replace')[:150]}", "steps": 0, "calls": 0}
    return {"answer": r["answer"], "cid": None, "error": "", "steps": 1, "calls": 1}


def method_fn(spec: str, no_local: bool):
    """Méthodes : simple | ask:<moteur> | orchestra[:<fournisseur>] | review[:<fournisseur>]
    (<moteur> = local ou l'identifiant d'un fournisseur, ex. groq ; voir --list)."""
    name, _, eng = spec.partition(":")
    pid = "" if eng in ("", "local") else eng
    participants = [f"p:{pid}", "auto", "auto"] if pid else (["local", "auto", "auto"] if eng == "local" else None)
    if name == "simple" and not eng:
        return None if no_local else run_simple
    if name in ("ask", "simple") and eng:
        engine = f"p:{pid}" if pid else "local"
        return None if (no_local and engine == "local") else (lambda a, t: run_ask(a, t, engine))
    if name in ("orchestra", "review"):
        def fn(a, t):
            return run_workshop(a, t, name, participants, not no_local)
        return fn
    return None


# ---------------------------------------------------------------- correction automatique

NUM_RE = re.compile(r"-?\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?|-?\d+(?:[.,]\d+)?")


def numbers_in(text: str) -> list[float]:
    """Nombres d'un texte, format français compris (« 20 553,62 », « 1 538.86 »)."""
    out = []
    for m in NUM_RE.findall(text or ""):
        s = re.sub(r"[   ]", "", m)
        if s.count(",") == 1 and s.count(".") == 0:
            s = s.replace(",", ".")
        elif "," in s and "." in s:
            s = s.replace(",", "")
        try:
            out.append(float(s))
        except ValueError:
            pass
    return out


def fold(s: str) -> str:
    """Minuscules sans accents ; tirets typographiques → « - » ; « euros » → « € »."""
    s = "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if unicodedata.category(c) != "Mn")
    s = re.sub(r"[\u2010-\u2015\u2212]", "-", s)
    s = re.sub(r"\b(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\b", r"\1-\2-\3", s)
    return re.sub(r"\beuros?\b|\beur\b", "€", s)


def run_code(answer: str, tests: list[str], timeout: int = 20) -> tuple[bool, str]:
    """Exécute le code de la réponse puis nos assertions et les test_* de la réponse, dans un processus isolé."""
    blocks = re.findall(r"```(?:python|py)?\s*\n([\s\S]*?)```", answer)
    if not blocks:
        return False, "aucun bloc de code"
    code = "\n\n".join(blocks)
    harness = code + "\n\n" + "\n".join(tests) + (
        "\n\nfor _n, _f in list(globals().items()):\n"
        "    if _n.startswith('test_') and callable(_f):\n"
        "        _f()\n"
        "print('TESTS OK')\n")
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "t.py"
        p.write_text(harness, encoding="utf-8")
        try:
            r = subprocess.run([sys.executable, "-I", str(p)], capture_output=True, text=True, timeout=timeout, cwd=d)
        except subprocess.TimeoutExpired:
            return False, "délai dépassé"
    if "TESTS OK" in r.stdout:
        return True, "tests réussis"
    return False, (r.stderr.strip().splitlines() or ["échec"])[-1][:150]


JUDGE_PROMPT = """Tu es un correcteur exigeant et impartial. Voici une consigne, une réponse, et des critères numérotés.
Pour CHAQUE critère, réponds 1 s'il est pleinement satisfait, 0 sinon. Ne sois pas indulgent.
Réponds UNIQUEMENT par du JSON : {{"notes": [1, 0, ...], "justification": "une phrase"}}

Consigne :
{task}

Critères :
{criteria}

Réponse à corriger :
{answer}"""


def judge_criteria(atom: "Atom", engine: str, task: dict, answer: str) -> tuple[float | None, str]:
    """Notation des critères qualitatifs par un modèle juge (via /api/bench/ask). (part réussie, note) ou (None, erreur)."""
    crit = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(task["criteria"]))
    prompt = JUDGE_PROMPT.format(task=task["text"], criteria=crit, answer=answer[:6000])
    try:
        r = atom.json("POST", "/api/bench/ask", {"message": prompt, "engine": engine})
    except Exception as e:  # noqa: BLE001
        return None, f"juge indisponible ({str(e)[:60]})"
    m = re.search(r"\{[\s\S]*\}", r.get("answer", ""))
    try:
        notes = [1 if int(x) else 0 for x in json.loads(m.group(0))["notes"]][:len(task["criteria"])]
    except (AttributeError, ValueError, KeyError, TypeError):
        return None, "juge : réponse illisible"
    if len(notes) < len(task["criteria"]):
        return None, "juge : notes incomplètes"
    missed = [c for c, n in zip(task["criteria"], notes, strict=True) if not n]
    return sum(notes) / len(notes), f"juge {sum(notes)}/{len(notes)}" + (f" (manque : {' | '.join(missed)})" if missed else "")


def grade(task: dict, answer: str, allow_code: bool, judge=None) -> tuple[str, str]:
    """(score, détail) ; score « 1 », « 0 », une fraction, ou « ? » (à noter à la main).
    judge : fonction (task, answer) → (part, note) pour les critères qualitatifs ; sans juge, à noter à la main."""
    if not answer.strip():
        return "0", "réponse vide"
    notes, parts = [], []
    if task.get("numbers"):
        found = numbers_in(answer)
        ok = [any(abs(f - x) <= max(0.01, abs(x) * 0.002) for f in found) for x in task["numbers"]]
        parts.append(sum(ok) / len(ok))
        notes.append("nombres " + " ".join(f"{x:g}{'✓' if o else '✗'}" for x, o in zip(task["numbers"], ok, strict=True)))
    if task.get("code_tests"):
        if allow_code:
            ok, why = run_code(answer, task["code_tests"])
            parts.append(1.0 if ok else 0.0)
            notes.append(why)
        else:
            notes.append("code non exécuté (--run-code)")
    if task.get("contains"):
        miss = [w for w in task["contains"] if fold(w) not in fold(answer)]
        parts.append(1.0 - len(miss) / len(task["contains"]))
        if miss:
            notes.append("manque : " + ", ".join(miss))
    if task.get("sources"):
        cited = bool(re.search(r"\[\d+\]|https?://", answer))
        parts.append(1.0 if cited else 0.0)
        notes.append("sources citées" if cited else "aucune source")
    if task.get("regex"):
        ok = [bool(re.search(rx, fold(answer), re.I)) for rx in task["regex"]]
        parts.append(sum(ok) / len(ok))
        if not all(ok):
            notes.append("motif attendu absent")
    if task.get("forbid"):
        hit = [w for w in task["forbid"] if fold(w) in fold(answer)]
        parts.append(0.0 if hit else 1.0)
        if hit:
            notes.append("piège : " + ", ".join(hit))
    if task.get("criteria") and judge:
        part, note = judge(task, answer)
        notes.append(note)
        if part is not None:
            parts.append(part)
    elif task.get("criteria"):
        notes.append("à noter à la main : " + " | ".join(task["criteria"]))
        if not parts:
            return "?", "; ".join(notes)
    if not parts:
        return "?", "; ".join(notes) or "aucun critère automatique"
    s = sum(parts) / len(parts)
    return (str(round(s, 2)) if 0 < s < 1 else str(int(s))), "; ".join(notes)


# ---------------------------------------------------------------- rapport

def report(rows: list[dict], out: Path, stats: dict | None) -> str:
    methods = list(dict.fromkeys(r["method"] for r in rows))
    lines = [f"# Banc d'essai Atom — {time.strftime('%d/%m/%Y %H:%M')}", "",
             "| Méthode | Score moyen (auto) | Réussites | Durée moyenne | Appels moyens | Erreurs |", "|---|---|---|---|---|---|"]
    for m in methods:
        rs = [r for r in rows if r["method"] == m]
        auto = [float(r["score"]) for r in rs if r["score"] not in ("?", "")]
        avg = sum(auto) / len(auto) if auto else 0
        wins = sum(1 for x in auto if x >= 1)
        dur = sum(float(r["seconds"]) for r in rs) / len(rs)
        calls = sum(float(r["calls"] or 0) for r in rs) / len(rs)
        lines.append(f"| {m} | {avg:.2f} | {wins}/{len(auto)} | {dur:.0f} s | {calls:.1f} | {sum(1 for r in rs if r['error'])} |")
    lines += ["", "## Détail par tâche", "", "| Tâche | Méthode | Score | Durée | Appels | Détail |", "|---|---|---|---|---|---|"]
    for r in rows:
        extra = f" · vérif. {r['verified']}" if r.get("verified") else ""
        extra += f" · escalades {r['escalated']}" if r.get("escalated") else ""
        extra += f" · échecs {r['failures']}" if r.get("failures") else ""
        lines.append(f"| {r['task']} | {r['method']} | {r['score']} | {float(r['seconds']):.0f} s | {r['calls']} | "
                     f"{(r['detail'] + extra + (' · ERREUR ' + r['error'] if r['error'] else '')).replace('|', '/')} |")
    if stats:
        lines += ["", "## Échecs cumulés de l'orchestration", "", "```json", json.dumps(stats, ensure_ascii=False, indent=2), "```"]
    lines += ["", "Les scores « ? » (rédaction) sont à noter à la main dans results.csv après lecture de answers/."]
    text = "\n".join(lines) + "\n"
    (out / "rapport.md").write_text(text, encoding="utf-8")
    return text


# ---------------------------------------------------------------- programme

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--url", default=os.getenv("ATOM_BENCH_URL", "http://localhost:8000"))
    ap.add_argument("--tasks", default=str(HERE / "tasks.json"), help="fichier de tâches (JSON)")
    ap.add_argument("--methods", default="simple,orchestra", help="simple, ask:<moteur>, orchestra[:<moteur>], review[:<moteur>]")
    ap.add_argument("--no-local", action="store_true", help="n'utilise jamais le modèle local")
    ap.add_argument("--list", action="store_true", help="liste les moteurs disponibles puis quitte")
    ap.add_argument("--only", default="", help="identifiants de tâches, séparés par des virgules")
    ap.add_argument("--repeat", type=int, default=1, help="répétitions (les petits modèles varient d'un essai à l'autre)")
    ap.add_argument("--timeout", type=int, default=1800, help="délai max par réponse, en secondes")
    ap.add_argument("--run-code", action="store_true", help="exécute le code produit pour le vérifier (processus isolé, -I)")
    ap.add_argument("--judge", default="", help="moteur juge pour les critères qualitatifs (ex. groq) ; choisis-en un "
                    "autre que ceux comparés")
    ap.add_argument("--hard", action="store_true", help="tâches difficiles et pièges (bench/tasks_hard.json)")
    ap.add_argument("--keep", action="store_true", help="garde les conversations créées dans Atom (supprimées sinon)")
    a = ap.parse_args()

    if a.hard and a.tasks == str(HERE / "tasks.json"):
        a.tasks = str(HERE / "tasks_hard.json")
    tasks = json.loads(Path(a.tasks).read_text(encoding="utf-8"))
    if a.only:
        wanted = set(a.only.split(","))
        tasks = [t for t in tasks if t["id"] in wanted]
    methods = [m for m in a.methods.split(",") if m]
    fns = {m: method_fn(m, a.no_local) for m in methods}
    bad = [m for m, f in fns.items() if f is None]
    if (bad or not tasks) and not a.list:
        sys.exit(f"Méthode inconnue ou incompatible avec --no-local : {bad}" if bad else "Aucune tâche sélectionnée.")

    atom = Atom(a.url, a.timeout)
    password = os.getenv("ATOM_BENCH_PASSWORD", "")
    if not password:
        if not sys.stdin.isatty():
            # En arrière-plan (nohup … &), demander le mot de passe bloquerait le processus (état « Stopped »).
            sys.exit("Mot de passe absent : exporte ATOM_BENCH_PASSWORD avant de lancer le script en arrière-plan.")
        password = getpass.getpass("Mot de passe d'Atom : ")
    atom.login(password)
    if a.list:
        opts = atom.json("GET", "/api/workshop")["options"]
        print("Moteurs disponibles (à utiliser après « ask: », « orchestra: »…) :")
        print("  local            " + next((o["label"] for o in opts if o["id"] == "local"), "modèle local"))
        for o in opts:
            if o["id"].startswith("p:"):
                print(f"  {o['id'][2:]:<16} {o['label']} · famille {o.get('family', '?')} · force {o.get('strength', '?')}")
        return
    out = HERE / "results" / time.strftime("%Y-%m-%d_%H%M")
    (out / "answers").mkdir(parents=True, exist_ok=True)
    fields = ["task", "kind", "method", "run", "score", "seconds", "calls", "steps", "difficulty", "verified",
              "escalated", "failures", "error", "detail"]
    rows: list[dict] = []
    total = len(tasks) * len(methods) * a.repeat
    n = 0
    with open(out / "results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for rep in range(1, a.repeat + 1):
            for t in tasks:
                for m in methods:
                    n += 1
                    print(f"[{n}/{total}] {t['id']} · {m} · essai {rep} … ", end="", flush=True)
                    t0 = time.time()
                    try:
                        res = fns[m](atom, t["text"])
                    except Exception as e:  # noqa: BLE001
                        res = {"answer": "", "cid": None, "error": str(e)[:200], "steps": 0, "calls": 0}
                    secs = time.time() - t0
                    judge = (lambda tk, ans: judge_criteria(atom, a.judge if ":" in a.judge else f"p:{a.judge}"
                                                            if a.judge != "local" else "local", tk, ans)) if a.judge else None
                    score, detail = grade(t, res["answer"], a.run_code, judge)
                    row = {"task": t["id"], "kind": t.get("kind", ""), "method": m, "run": rep, "score": score,
                           "seconds": f"{secs:.1f}", "detail": detail, **{k: res.get(k, "") for k in fields if k in res}}
                    rows.append(row)
                    w.writerow(row)
                    f.flush()
                    (out / "answers" / f"{t['id']}__{m}__{rep}.md").write_text(
                        f"# {t['id']} · {m} · essai {rep}\n\n**Tâche :** {t['text']}\n\n**Score :** {score} — {detail}\n\n"
                        f"**Durée :** {secs:.0f} s\n\n---\n\n{res['answer']}\n", encoding="utf-8")
                    print(f"score {score} · {secs:.0f} s" + (f" · ERREUR {res['error']}" if res.get("error") else ""))
                    if res.get("cid") and not a.keep:
                        try:
                            atom.json("DELETE", f"/api/conversations/{res['cid']}")
                        except Exception:  # noqa: BLE001
                            pass
    stats = None
    try:
        stats = atom.json("GET", "/api/orchestra/stats")
        (out / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    print("\n" + report(rows, out, stats))
    print(f"Résultats : {out}")


if __name__ == "__main__":
    main()
