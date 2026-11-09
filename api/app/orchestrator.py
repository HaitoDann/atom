"""Orchestration de petits modèles : découper, exécuter, vérifier, corriger, escalader, assembler.

Principes tirés des études (voir README → Orchestration) :
1. Vérification EXTERNE d'abord (exécution Python, sources citées, format) ; un modèle juge seulement quand rien
   d'autre n'est possible, et jamais le modèle qui a écrit (autre famille si possible) — un modèle se corrige mal seul.
2. Plusieurs essais puis vote (ou meilleur des N par un juge) plutôt qu'un débat : moins cher, aussi bon.
3. Un chef d'orchestre qui découpe avec des consignes strictes (objectif, entrées, format, critère de réussite) ;
   chaque exécutant reçoit un contexte court : la demande et le résumé des étapes dont il dépend.
4. Routage par difficulté : simple = un appel ; moyenne = meilleur des N ; difficile = plan complet.
   Petit modèle local d'abord pour exécuter, modèle plus fort pour planifier, juger, et en cas d'échecs répétés.
5. Assemblage « mixture of agents » : un agrégateur fusionne les résultats des étapes.
6. Débat court (un seul échange d'arbitrage) seulement quand les essais se contredisent.
7. Trace de chaque étape (essais, vérifications, échecs classés) et statistiques des échecs.

Confidentialité : comme l'atelier, seuls la demande et le fil récent partent — ni souvenirs, ni bibliothèque.
"""

from __future__ import annotations

import contextvars
import json
import os
import re
import time
from collections import Counter
from typing import AsyncIterator

from . import db, workshop

import logging

log = logging.getLogger("atom.orchestrator")

SAMPLES = max(1, min(5, int(os.getenv("ATOM_ORCH_SAMPLES", "3"))))       # essais pour un vote / meilleur des N
RETRIES = max(0, min(3, int(os.getenv("ATOM_ORCH_RETRIES", "2"))))       # corrections avant d'escalader
MAX_STEPS = max(1, min(8, int(os.getenv("ATOM_ORCH_MAX_STEPS", "5"))))
CTX_CHARS = 1500                                                         # résumé transmis d'une étape à l'autre
KINDS = ("recherche", "calcul", "code", "redaction", "analyse")
# Familles d'échec (inspirées de la taxonomie MAST : consignes, coordination, vérification) + outils.
FAILURES = ("consigne", "format", "verification", "outil", "contradiction")

BASE = workshop.BASE.replace("atelier", "équipe orchestrée")

# ---------------------------------------------------------------- routage par difficulté

MULTI_RE = re.compile(r"\b(puis|ensuite|et enfin|étape|étapes|d'abord|plusieurs|rapport|plan complet|cherche|"
                      r"recherche|calcule|compare|analyse|synthèse|vérifie)\b", re.I)
CALC_RE = re.compile(r"\b(calcule|combien|pourcentage|moyenne|somme|total|intérêts?|convertis|résous|équation)\b|\d+\s*[-+*/×÷^%]\s*\d+", re.I)
SEARCH_RE = re.compile(r"\b(actualité|récent|dernier|dernière|aujourd'hui|cette année|prix|cherche|recherche|source)\b", re.I)


def difficulty(message: str) -> str:
    """« simple » (un appel), « moyenne » (meilleur des N vérifié) ou « difficile » (plan complet)."""
    m = message or ""
    hits = len(set(x.lower() for x in MULTI_RE.findall(m)))
    if len(m) > 700 or hits >= 3 or m.count("\n") > 10:
        return "difficile"
    if len(m) > 160 or hits >= 1 or CALC_RE.search(m) or workshop.is_deliverable(m):
        return "moyenne"
    return "simple"


def guess_kind(text: str) -> str:
    if workshop.is_deliverable(text):
        return "code"
    if CALC_RE.search(text):
        return "calcul"
    if SEARCH_RE.search(text):
        return "recherche"
    return "redaction"


# ---------------------------------------------------------------- moteurs

def engines(worker: str | None = None, allow_local: bool = True) -> dict:
    """Rôles concrets : exécutant (petit modèle d'abord, ou celui imposé), planificateur/agrégateur (le plus fort),
    juge (autre famille que l'exécutant), échelle d'escalade (du plus faible au plus fort).
    allow_local=False : le modèle local n'intervient nulle part (comparaison de fournisseurs distants)."""
    cands = workshop.candidates()                  # du plus fort au plus faible, local en dernier
    if not allow_local:
        cands = [c for c in cands if c != "local"] or cands
    strongest = cands[0]
    worker = worker if worker and (worker in cands or worker.startswith("p:")) else ("local" if allow_local else cands[-1])
    fam = workshop._info(worker)[1]
    judge = next((c for c in cands if c != worker and workshop._info(c)[1] != fam),
                 next((c for c in cands if c != worker), strongest))
    rank = {c: i for i, c in enumerate(cands)}
    stronger = [c for c in reversed(cands) if c != worker and rank.get(c, 99) < rank.get(worker, 99)]
    ladder = [worker] + stronger
    return {"worker": worker, "planner": strongest, "judge": judge, "ladder": ladder, "allow_local": allow_local,
            "same_family_judge": workshop._info(judge)[1] == fam}


ALLOW_LOCAL = contextvars.ContextVar("orch_allow_local", default=True)


async def _ask(engine: str, messages: list[dict]) -> tuple[str, str]:
    """Texte complet d'un appel (avec relais) et le moteur réellement utilisé."""
    switched: list = []
    out = "".join([t async for t in workshop._gen(engine, messages, lambda e, why: switched.append(e),
                                                  allow_local=ALLOW_LOCAL.get())])
    return workshop.TAG_RE.sub("", workshop.THINK_RE.sub("", out)).strip(), (switched[-1] if switched else engine)


# ---------------------------------------------------------------- planification

PLANNER = (" Ton rôle : CHEF D'ORCHESTRE. Découpe la demande en {n} étapes au plus, chacune simple, courte et "
           "vérifiable, exécutable par un PETIT modèle. Réponds UNIQUEMENT par du JSON :\n"
           '{{"steps": [{{"id": "s1", "goal": "objectif précis", "kind": "recherche|calcul|code|redaction|analyse", '
           '"query": "requête web (recherche seulement)", "inputs": ["ids des étapes utiles"], '
           '"output": "format attendu", "check": "critère de réussite vérifiable"}}]}}\n'
           "Règles : une seule étape si la demande est simple ; « calcul » pour tout chiffre à calculer (il sera "
           "exécuté en Python) ; « recherche » pour un fait récent ou à sourcer ; pas d'étape de relecture ni "
           "d'assemblage (c'est automatique). /no_think")


def parse_plan(text: str, message: str) -> list[dict]:
    """Plan JSON robuste ; à défaut, une seule étape déduite de la demande."""
    steps = []
    m = re.search(r"\{[\s\S]*\}", text or "")
    if m:
        try:
            raw = json.loads(m.group(0)).get("steps") or []
        except (ValueError, AttributeError):
            raw = []
        for i, s in enumerate(raw[:MAX_STEPS]):
            if not isinstance(s, dict) or not str(s.get("goal", "")).strip():
                continue
            kind = s.get("kind") if s.get("kind") in KINDS else "redaction"
            steps.append({"id": str(s.get("id") or f"s{i + 1}"), "goal": str(s["goal"])[:500], "kind": kind,
                          "query": str(s.get("query") or s["goal"])[:200],
                          "inputs": [str(x) for x in (s.get("inputs") or []) if isinstance(x, (str, int))][:5],
                          "output": str(s.get("output") or "")[:200], "check": str(s.get("check") or "")[:300]})
    return steps or [{"id": "s1", "goal": message[:2000], "kind": guess_kind(message), "query": message[:200],
                      "inputs": [], "output": "", "check": ""}]


# ---------------------------------------------------------------- vérification

def answer_key(text: str) -> str:
    """Réponse « courte » normalisée pour voter : dernier nombre, ou dernière ligne non vide."""
    nums = re.findall(r"-?\d+(?:[.,]\d+)?", text or "")
    if nums:
        return nums[-1].replace(",", ".").rstrip("0").rstrip(".") or "0"
    lines = [x.strip().lower() for x in (text or "").splitlines() if x.strip()]
    return re.sub(r"[^\w]+", " ", lines[-1]).strip()[:120] if lines else ""


def vote(candidates: list[str]) -> tuple[str | None, float]:
    """(gagnant, part des voix) ; None s'il n'y a pas de majorité."""
    keys = [answer_key(c) for c in candidates]
    if not keys:
        return None, 0.0
    key, n = Counter(keys).most_common(1)[0]
    share = n / len(keys)
    if n < 2 and len(keys) > 1:
        return None, share
    return candidates[keys.index(key)], share


def check_format(step: dict, text: str) -> str:
    """Contrôles sans modèle ; renvoie la raison de l'échec ou ''."""
    if not text.strip():
        return "réponse vide"
    if len(text) < 3:
        return "réponse trop courte"
    if re.search(r"(Lorem ipsum|Nom de votre entreprise|\[à compléter\])", text, re.I):
        return "texte d'exemple laissé tel quel"
    if step["kind"] == "recherche" and step.get("_sources") and not re.search(r"\[\d+\]", text):
        return "aucune source citée alors que des résultats étaient fournis"
    if re.search(r"json", step.get("output", ""), re.I):
        try:
            json.loads(re.search(r"[\[{][\s\S]*[\]}]", text).group(0))
        except (AttributeError, ValueError):
            return "JSON attendu mais invalide"
    return ""


JUDGE = (" Ton rôle : VÉRIFICATEUR. Tu n'as PAS écrit ce résultat. Vérifie-le strictement contre l'objectif et le "
         "critère de réussite. Réponds en 5 lignes au plus : les problèmes concrets (faits faux, consigne non "
         "respectée, calcul faux, manque), puis exactement « Verdict : OK » ou « Verdict : À corriger ». "
         "N'invente pas de problème : si c'est juste, dis OK. /no_think")
PICK = (" Ton rôle : ARBITRE. Plusieurs candidats répondent au même objectif. Compare-les sur l'exactitude et le "
        "respect du critère. Réponds par une ligne « Choix : N » (numéro du meilleur), puis une ligne de justification. /no_think")


def judge_ok(text: str) -> bool:
    return bool(re.search(r"verdict\s*:\s*ok\b", (text or "").lower()))


def _step_brief(step: dict, request: str, ctx: str) -> str:
    out = [f"Demande de l'utilisateur (contexte) :\n{request[:2500]}", f"Ton objectif pour cette étape : {step['goal']}"]
    if step.get("output"):
        out.append(f"Format attendu : {step['output']}")
    if step.get("check"):
        out.append(f"Critère de réussite : {step['check']}")
    if ctx:
        out.append(f"Résultats des étapes précédentes (résumés) :\n{ctx}")
    return "\n\n".join(out)


# ---------------------------------------------------------------- exécution d'une étape

SYS_EXEC = {
    "redaction": " Réalise UNIQUEMENT l'objectif de l'étape, précisément et complètement, dans le format attendu.",
    "analyse": " Analyse avec rigueur : distingue faits, hypothèses et conclusions. Réalise uniquement l'objectif.",
    "code": " Écris du code complet et fonctionnel tel quel, chaque fichier en entier dans un bloc de code.",
    "recherche": " Réponds à l'objectif à partir des résultats web fournis uniquement, en citant [n]. "
                 "Si les résultats ne suffisent pas, dis-le.",
    "calcul": " Écris un script Python autonome (bibliothèque standard) qui calcule le résultat et l'affiche avec "
              "print, dans un seul bloc ```python```. Puis donne en une ligne le résultat attendu.",
}


def _code_block(reply: str) -> str:
    m = re.search(r"```(?:python|py)?\s*\n([\s\S]*?)```", reply)
    return m.group(1).strip() if m else ""


async def _external(step: dict, text: str) -> tuple[str, str]:
    """Vérification par un outil : (texte éventuellement enrichi, raison d'échec ou '')."""
    if step["kind"] != "calcul":
        return text, ""
    code = _code_block(text)
    if not code:
        return text, "aucun script Python fourni pour le calcul"
    from . import sandbox
    if not sandbox.enabled():
        step["_tool"] = "indisponible"
        return text, ""                               # pas de bac à sable : on se rabat sur le vote
    try:
        rc, out, _ = await sandbox.run_python({}, code, timeout=60, packages=False)
    except Exception as e:                             # noqa: BLE001
        step["_tool"] = f"erreur : {e}"
        return text, ""
    step["_tool"] = "exécuté"
    if rc != 0:
        return text, f"le script a échoué (code {rc}) : {out.strip()[-400:]}"
    return f"{text}\n\nRésultat de l'exécution :\n```\n{out.strip()[:1500]}\n```", ""


async def run_step(step: dict, request: str, ctx: str, eng: dict, level: str, trace: dict) -> tuple[str, str]:
    """Exécute une étape avec essais, vérification externe, juge, corrections et escalade. Renvoie (texte, moteur)."""
    brief = _step_brief(step, request, ctx)
    if step["kind"] == "recherche":
        from . import search
        if search.enabled():
            try:
                res = await search.search(step["query"])
                if res:
                    step["_sources"] = len(res)
                    brief += "\n\n" + search.prompt_block(step["query"], res, time.strftime("%Y-%m-%d"))
            except Exception as e:                     # noqa: BLE001
                trace["failures"].append(("outil", f"recherche : {e}"))
    sys = BASE + SYS_EXEC[step["kind"]] + (workshop.DELIVERABLE_RULES if step["kind"] == "code" else "")
    critique, best, used = "", "", eng["worker"]
    ladder = eng["ladder"]
    rung = 0
    n = SAMPLES if level != "simple" else 1
    for attempt in range(RETRIES + 1 + max(0, len(ladder) - 1)):
        engine = ladder[min(rung, len(ladder) - 1)]
        user = brief + (f"\n\nTa tentative précédente a été refusée. Problèmes à corriger :\n{critique}\n\n"
                        f"Tentative précédente :\n{best[:3000]}" if critique else "")
        msgs = [{"role": "system", "content": sys}, {"role": "user", "content": user}]
        # Plusieurs essais seulement à la première tentative (après, la critique guide la correction).
        k = n if attempt == 0 else 1
        cands = []
        for _ in range(k):
            try:
                text, used = await _ask(engine, msgs)
            except Exception as e:                      # noqa: BLE001 — moteur indisponible : on monte d'un cran
                trace["failures"].append(("outil", f"{workshop.engine_label(engine)} indisponible : {str(e)[:150]}"))
                break
            text, why = await _external(step, text)
            why = why or check_format(step, text)
            trace["calls"] += 1
            if why:
                trace["failures"].append(("outil" if "script" in why else "format", why))
                critique = why
                best = text
                continue
            cands.append(text)
        trace["attempts"] += 1
        if not cands:
            unavailable = trace["failures"] and "indisponible" in trace["failures"][-1][1]
            rung += 1 if (attempt >= RETRIES or unavailable) else 0
            if unavailable:
                trace["escalated"] = True
            if rung >= len(ladder):
                break
            continue
        if len(cands) == 1:
            best = cands[0]
        else:
            winner, share = vote(cands) if step["kind"] in ("calcul", "analyse") else (None, 0.0)
            trace["vote"] = round(share, 2)
            if winner is not None:
                best = winner
            else:
                # Pas de majorité (ou texte long) : un arbitre choisit — c'est le seul « débat », un échange.
                if step["kind"] in ("calcul", "analyse"):
                    trace["failures"].append(("contradiction", "les essais se contredisent"))
                listing = "\n\n".join(f"Candidat {i + 1} :\n{c[:2500]}" for i, c in enumerate(cands))
                try:
                    pick, _ = await _ask(eng["judge"], [{"role": "system", "content": BASE + PICK},
                                                       {"role": "user", "content": f"{brief}\n\n{listing}"}])
                except Exception:                       # noqa: BLE001 — arbitre indisponible : premier candidat
                    pick = ""
                trace["calls"] += 1
                m = re.search(r"choix\s*:\s*(\d+)", pick.lower())
                idx = int(m.group(1)) - 1 if m else 0
                best = cands[idx] if 0 <= idx < len(cands) else cands[0]
        # Juge d'une autre famille, sauf si un outil a déjà validé le résultat.
        if step.get("_tool") == "exécuté" or level == "simple":
            trace["verified"] = "outil" if step.get("_tool") == "exécuté" else "format"
            return best, used
        try:
            verdict, _ = await _ask(eng["judge"], [{"role": "system", "content": BASE + JUDGE},
                                                  {"role": "user", "content": f"{brief}\n\nRésultat à vérifier :\n{best[:4000]}"}])
        except Exception as e:                          # noqa: BLE001 — juge indisponible : on garde le contrôle de format
            trace["failures"].append(("outil", f"juge indisponible : {str(e)[:150]}"))
            trace["verified"] = "format (juge indisponible)"
            return best, used
        trace["calls"] += 1
        if judge_ok(verdict):
            trace["verified"] = "juge" + (" (même famille)" if eng["same_family_judge"] else "")
            return best, used
        critique = verdict[:1200]
        trace["failures"].append(("verification", critique[:200]))
        if attempt >= RETRIES - 1:
            rung += 1                                   # escalade vers un modèle plus fort
            trace["escalated"] = True
        if rung >= len(ladder):
            break
    trace["verified"] = "non"
    return best or "(aucun résultat valide)", used


# ---------------------------------------------------------------- assemblage

AGGREGATE = (" Ton rôle : AGRÉGATEUR. Des étapes ont été réalisées et vérifiées par d'autres modèles. Fusionne-les en "
             "UNE réponse finale complète pour l'utilisateur : garde ce qui est juste, supprime les répétitions, "
             "conserve les sources [n] et les résultats de calcul exécutés, signale ce qui reste non vérifié. "
             "Ne parle pas des étapes ni de l'équipe.")


def record_stats(failures: list[tuple[str, str]], verified: list[str]) -> None:
    """Compteurs cumulés des échecs par famille et des vérifications (réglages → Atelier)."""
    try:
        s = json.loads(db.kv_get("orchestra_stats") or "{}")
    except ValueError:
        s = {}
    s["runs"] = s.get("runs", 0) + 1
    for cat, _ in failures:
        s.setdefault("failures", {})[cat] = s.get("failures", {}).get(cat, 0) + 1
    for v in verified:
        key = v.split(" ")[0]
        s.setdefault("verified", {})[key] = s.get("verified", {}).get(key, 0) + 1
    db.kv_set("orchestra_stats", json.dumps(s))


def stats() -> dict:
    try:
        s = json.loads(db.kv_get("orchestra_stats") or "{}")
    except ValueError:
        s = {}
    return {"runs": s.get("runs", 0), "failures": {k: s.get("failures", {}).get(k, 0) for k in FAILURES},
            "verified": s.get("verified", {})}


def preview(message: str) -> dict:
    level = difficulty(message)
    eng = engines()
    calls = 1 if level == "simple" else (1 + SAMPLES + 1 if level == "moyenne" else 1 + 3 * (SAMPLES + 1) + 1)
    steps = ([("Exécutant", eng["worker"])] if level == "simple" else
             [("Exécutant", eng["worker"]), ("Vérificateur", eng["judge"])] if level == "moyenne" else
             [("Chef d'orchestre", eng["planner"]), ("Exécutant", eng["worker"]),
              ("Vérificateur", eng["judge"]), ("Assemblage", eng["planner"])])
    warn = []
    if eng["same_family_judge"]:
        warn.append("Aucun modèle d'une autre famille n'est configuré : le juge est de la même famille que l'exécutant "
                    "(il repère moins bien ses erreurs). Les vérifications par outil restent actives.")
    return {"difficulty": level, "steps": steps, "calls": calls, "warnings": warn}


async def run(request: str, record: list, worker: str | None = None, allow_local: bool = True) -> AsyncIterator[dict]:
    """Événements au format de l'atelier (plan, step start/token/done, token). Remplit `record` ;
    le dernier élément yieldé est {"type": "_final", "text": …, "orchestra": …} (consommé par workshop.run)."""
    level = difficulty(request)
    eng = engines(worker, allow_local)
    ALLOW_LOCAL.set(allow_local)
    t0 = time.time()
    info = {"difficulty": level, "steps": [], "judge": workshop.engine_label(eng["judge"]),
            "same_family_judge": eng["same_family_judge"]}
    idx = 0

    def node(role: str, engine: str) -> dict:
        return {"role": role, "engine": workshop.engine_label(engine), "remote": engine.startswith("p:")}

    # 1. Planification (seulement pour les demandes difficiles : c'est l'étape qui demande le modèle le plus fort).
    if level == "difficile":
        yield dict(type="plan", pattern="orchestra", name=workshop.PATTERNS["orchestra"],
                   steps=[node("Chef d'orchestre", eng["planner"]), node("Étapes", eng["worker"]), node("Assemblage", eng["planner"])])
        yield dict(type="step", status="start", index=0, role="Chef d'orchestre", engine=workshop.engine_label(eng["planner"]), final=False)
        t = time.time()
        try:
            raw, used = await _ask(eng["planner"], [{"role": "system", "content": BASE + PLANNER.format(n=MAX_STEPS)},
                                                   {"role": "user", "content": request}])
        except Exception as e:                          # noqa: BLE001 — chef indisponible : une seule étape
            log.info("orchestration : chef d'orchestre indisponible (%s), une seule étape", e)
            raw, used = "", eng["planner"]
        steps = parse_plan(raw, request)
        summary = "\n".join(f"{i + 1}. [{s['kind']}] {s['goal']}" for i, s in enumerate(steps))
        yield dict(type="step", status="done", index=0, text=summary, seconds=round(time.time() - t, 1))
        record.append({"role": "Chef d'orchestre", "engine": workshop.engine_label(used), "text": summary,
                       "seconds": round(time.time() - t, 1)})
        idx = 1
    else:
        steps = parse_plan("", request)
    roles = [f"{i + 1}. {s['kind'].capitalize()}" for i, s in enumerate(steps)]
    assemble = len(steps) > 1
    plan_nodes = ([dict(node("Chef d'orchestre", eng["planner"]), done=True)] if idx else []) + \
        [node(r, eng["worker"]) for r in roles] + ([node("Assemblage", eng["planner"])] if assemble else [])
    yield dict(type="plan", pattern="orchestra", name=workshop.PATTERNS["orchestra"], steps=plan_nodes)

    # 2. Exécution, étape par étape, avec un contexte court.
    results: dict[str, str] = {}
    all_fail, verified = [], []
    for i, step in enumerate(steps):
        final = not assemble and i == len(steps) - 1
        yield dict(type="step", status="start", index=idx, role=roles[i], engine=workshop.engine_label(eng["worker"]), final=final)
        ctx_ids = step["inputs"] or list(results)[-2:]
        ctx = "\n\n".join(f"[{k}] {results[k][:CTX_CHARS]}" for k in ctx_ids if k in results)
        trace = {"calls": 0, "attempts": 0, "failures": [], "verified": "", "escalated": False}
        t = time.time()
        text, used = await run_step(step, request, ctx, eng, level, trace)
        results[step["id"]] = text
        label = workshop.engine_label(used) + (" (relais)" if used != eng["worker"] else "")
        if used != eng["worker"]:
            yield dict(type="step", status="engine", index=idx, engine=label, reason="escalade ou relais")
        note = f"\n\n*Vérification : {trace['verified'] or 'aucune'} · {trace['calls']} appel(s)" + \
               (" · escaladé" if trace["escalated"] else "") + "*"
        if final:
            for piece in re.findall(r"\S+\s*|\s+", text):
                yield dict(type="token", text=piece)
        yield dict(type="step", status="done", index=idx, text=text + ("" if final else note), seconds=round(time.time() - t, 1))
        record.append({"role": roles[i], "engine": label, "text": text, "seconds": round(time.time() - t, 1)})
        info["steps"].append({"goal": step["goal"], "kind": step["kind"], "calls": trace["calls"], "attempts": trace["attempts"],
                              "verified": trace["verified"], "escalated": trace["escalated"], "vote": trace.get("vote"),
                              "tool": step.get("_tool"), "failures": [{"type": a, "detail": b} for a, b in trace["failures"]]})
        all_fail += trace["failures"]
        verified.append(trace["verified"] or "non")
        idx += 1

    # 3. Assemblage par l'agrégateur (le plus fort), en flux.
    final_text = results[steps[-1]["id"]] if steps else ""
    if assemble:
        yield dict(type="step", status="start", index=idx, role="Assemblage", engine=workshop.engine_label(eng["planner"]), final=True)
        parts = "\n\n".join(f"Étape {i + 1} ({s['goal']}) :\n{results[s['id']][:3000]}" for i, s in enumerate(steps))
        msgs = [{"role": "system", "content": BASE + AGGREGATE},
                {"role": "user", "content": f"Demande :\n{request[:3000]}\n\nRésultats des étapes :\n{parts}"}]
        t, text, sent, switched = time.time(), "", 0, []
        try:
            async for tok in workshop._gen(eng["planner"], msgs, lambda e, why: switched.append(e), allow_local=allow_local):
                text += tok
                clean = workshop.TAG_RE.sub("", workshop.THINK_RE.sub("", text))
                if len(text) < 30 and "]" not in text[:25]:
                    continue
                if clean[sent:]:
                    yield dict(type="token", text=clean[sent:])
                    sent = len(clean)
        except Exception as e:                          # agrégateur indisponible : résultats bout à bout
            if sent:
                raise
            log.info("orchestration : agrégateur indisponible (%s), résultats juxtaposés", e)
            text = "\n\n".join(f"**{s['goal']}**\n\n{results[s['id']]}" for s in steps)
        clean = workshop.TAG_RE.sub("", workshop.THINK_RE.sub("", text))
        if clean[sent:]:
            yield dict(type="token", text=clean[sent:])
        final_text = clean.strip() or final_text
        label = workshop.engine_label(switched[-1] if switched else eng["planner"])
        yield dict(type="step", status="done", index=idx, text=final_text, seconds=round(time.time() - t, 1))
        record.append({"role": "Assemblage", "engine": label, "text": final_text, "seconds": round(time.time() - t, 1)})
    info["seconds"] = round(time.time() - t0, 1)
    info["calls"] = sum(s["calls"] for s in info["steps"]) + (1 if level == "difficile" else 0) + (1 if assemble else 0)
    record_stats(all_fail, verified)
    log.info("orchestration %s : %d étapes, %d appels, %.0f s, échecs %s", level, len(steps), info["calls"],
             info["seconds"], dict(Counter(a for a, _ in all_fail)))
    yield {"type": "_final", "text": final_text, "orchestra": info}
