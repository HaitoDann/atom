"""Orchestration de petits modèles : routage, plan, vote, vérification, corrections, escalade, statistiques."""

import asyncio
import json

import pytest


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("text,level", [
    ("Salut !", "simple"),
    ("Calcule 15 % de 240", "moyenne"),
    ("Cherche les prix actuels, puis compare-les, ensuite rédige une synthèse et enfin vérifie les calculs", "difficile"),
])
def test_difficulty(text, level):
    from app import orchestrator
    assert orchestrator.difficulty(text) == level


def test_vote_majority_and_contradiction():
    from app import orchestrator
    win, share = orchestrator.vote(["Le total est 42.", "Donc 42,0", "Je trouve 41"])
    assert orchestrator.answer_key(win) == "42" and share == pytest.approx(2 / 3)
    win, _ = orchestrator.vote(["1", "2", "3"])
    assert win is None


def test_parse_plan_robust():
    from app import orchestrator
    raw = 'Voici : {"steps": [{"id": "a", "goal": "Calculer", "kind": "calcul"}, {"goal": "Rédiger", "kind": "bizarre", "inputs": ["a"]}, {"x": 1}]}'
    steps = orchestrator.parse_plan(raw, "demande")
    assert [s["kind"] for s in steps] == ["calcul", "redaction"] and steps[1]["inputs"] == ["a"]
    fallback = orchestrator.parse_plan("pas du json", "Calcule 2 + 2")
    assert len(fallback) == 1 and fallback[0]["kind"] == "calcul"


def test_check_format():
    from app import orchestrator
    assert orchestrator.check_format({"kind": "redaction"}, "")
    assert "exemple" in orchestrator.check_format({"kind": "redaction"}, "Bienvenue chez Nom de votre entreprise")
    assert "source" in orchestrator.check_format({"kind": "recherche", "_sources": 3}, "Réponse sans citation")
    assert orchestrator.check_format({"kind": "recherche", "_sources": 3}, "D'après [1], oui.") == ""
    assert "JSON" in orchestrator.check_format({"kind": "analyse", "output": "JSON"}, "pas de json")


def _fake(monkeypatch, replies):
    """Remplace les appels aux modèles : `replies(engine, system, user)` → texte. Journal des appels renvoyé."""
    from app import orchestrator
    calls = []

    async def ask(engine, messages):
        sys, user = messages[0]["content"], messages[-1]["content"]
        calls.append((engine, sys, user))
        return replies(engine, sys, user), engine
    monkeypatch.setattr(orchestrator, "_ask", ask)
    return calls


def test_judge_critique_then_fix(monkeypatch):
    """Le juge refuse la 1re version : la critique est renvoyée à l'exécutant, qui corrige ; le juge n'est pas l'auteur."""
    from app import orchestrator
    monkeypatch.setattr(orchestrator, "SAMPLES", 1)
    state = {"n": 0}

    def replies(engine, sys, user):
        if "VÉRIFICATEUR" in sys:
            state["n"] += 1
            return "Il manque la conclusion.\nVerdict : À corriger" if state["n"] == 1 else "Verdict : OK"
        return "Version corrigée avec conclusion" if "refusée" in user else "Version 1"
    calls = _fake(monkeypatch, replies)
    eng = {"worker": "local", "planner": "p:x", "judge": "p:y", "ladder": ["local", "p:x"], "same_family_judge": False}
    trace = {"calls": 0, "attempts": 0, "failures": [], "verified": "", "escalated": False}
    step = orchestrator.parse_plan("", "Rédige un texte")[0]
    text, used = run(orchestrator.run_step(step, "Rédige un texte", "", eng, "moyenne", trace))
    assert text == "Version corrigée avec conclusion" and trace["verified"] == "juge"
    assert any("Il manque la conclusion" in u for _, _, u in calls)            # critique transmise
    assert all(e == "p:y" for e, s, _ in calls if "VÉRIFICATEUR" in s)         # juge ≠ exécutant
    assert trace["failures"][0][0] == "verification"


def test_escalation_after_repeated_failures(monkeypatch):
    from app import orchestrator
    monkeypatch.setattr(orchestrator, "SAMPLES", 1)
    monkeypatch.setattr(orchestrator, "RETRIES", 1)

    def replies(engine, sys, user):
        if "VÉRIFICATEUR" in sys:
            return "Verdict : OK" if "par le fort" in user else "Faux.\nVerdict : À corriger"
        return "Réponse par le fort" if engine == "p:fort" else "Réponse faible"
    _fake(monkeypatch, replies)
    eng = {"worker": "local", "planner": "p:fort", "judge": "p:juge", "ladder": ["local", "p:fort"], "same_family_judge": False}
    trace = {"calls": 0, "attempts": 0, "failures": [], "verified": "", "escalated": False}
    step = orchestrator.parse_plan("", "Explique la photosynthèse")[0]
    text, used = run(orchestrator.run_step(step, "Explique", "", eng, "moyenne", trace))
    assert used == "p:fort" and trace["escalated"] and "fort" in text


def test_vote_then_arbiter_on_contradiction(monkeypatch):
    """Essais contradictoires sur une analyse : l'arbitre (un seul échange) choisit."""
    from app import orchestrator
    monkeypatch.setattr(orchestrator, "SAMPLES", 3)
    answers = iter(["Résultat 10", "Résultat 20", "Résultat 30"])

    def replies(engine, sys, user):
        if "ARBITRE" in sys:
            return "Choix : 2\nC'est le seul cohérent."
        if "VÉRIFICATEUR" in sys:
            return "Verdict : OK"
        return next(answers)
    _fake(monkeypatch, replies)
    eng = {"worker": "local", "planner": "p:x", "judge": "p:y", "ladder": ["local", "p:x"], "same_family_judge": False}
    trace = {"calls": 0, "attempts": 0, "failures": [], "verified": "", "escalated": False}
    step = {"id": "s1", "goal": "Analyse", "kind": "analyse", "query": "", "inputs": [], "output": "", "check": ""}
    text, _ = run(orchestrator.run_step(step, "Analyse", "", eng, "moyenne", trace))
    assert text == "Résultat 20" and ("contradiction", "les essais se contredisent") in trace["failures"]


def test_calc_verified_by_tool(monkeypatch):
    """Un calcul est exécuté en Python : un script en échec est renvoyé avec l'erreur, sans juge une fois validé."""
    from app import orchestrator, sandbox
    monkeypatch.setattr(orchestrator, "SAMPLES", 1)
    monkeypatch.setattr(sandbox, "enabled", lambda: True)
    runs = []

    async def run_python(files, code, timeout=180, packages=True):
        assert packages is False                     # calcul : bibliothèque standard, sans installation
        runs.append(code)
        return (1, "NameError: x", {}) if "x" in code else (0, "42\n", {})
    monkeypatch.setattr(sandbox, "run_python", run_python)

    def replies(engine, sys, user):
        assert "VÉRIFICATEUR" not in sys
        return "```python\nprint(6*7)\n```\n42" if "refusée" in user else "```python\nprint(x)\n```"
    _fake(monkeypatch, replies)
    eng = {"worker": "local", "planner": "p:x", "judge": "p:y", "ladder": ["local", "p:x"], "same_family_judge": False}
    trace = {"calls": 0, "attempts": 0, "failures": [], "verified": "", "escalated": False}
    step = orchestrator.parse_plan("", "Calcule 6 × 7")[0]
    text, _ = run(orchestrator.run_step(step, "Calcule 6 × 7", "", eng, "moyenne", trace))
    assert len(runs) == 2 and "Résultat de l'exécution" in text and trace["verified"] == "outil"
    assert trace["failures"][0][0] == "outil"


def test_full_run_plan_steps_and_assembly(client, monkeypatch):
    from app import orchestrator, workshop
    monkeypatch.setattr(orchestrator, "SAMPLES", 1)
    monkeypatch.setattr(orchestrator, "engines", lambda *a, **k: {"worker": "local", "planner": "local", "judge": "local",
                                                         "ladder": ["local"], "same_family_judge": True})

    def replies(engine, sys, user):
        if "CHEF D'ORCHESTRE" in sys:
            return json.dumps({"steps": [{"id": "a", "goal": "Lister", "kind": "redaction"},
                                         {"id": "b", "goal": "Résumer", "kind": "redaction", "inputs": ["a"]}]})
        if "VÉRIFICATEUR" in sys:
            return "Verdict : OK"
        return "liste" if "Lister" in user else "résumé"
    calls = _fake(monkeypatch, replies)

    async def gen(engine, messages, on_engine, **kw):
        assert "AGRÉGATEUR" in messages[0]["content"] and "liste" in messages[-1]["content"]
        for w in ["Réponse ", "finale ", "assemblée."]:
            yield w
    monkeypatch.setattr(workshop, "_gen", gen)
    msg = "D'abord liste les étapes, puis résume-les, ensuite vérifie et enfin compare plusieurs options"
    record = []

    async def collect():
        return [ev async for ev in orchestrator.run(msg, record)]
    events = run(collect())
    final = events[-1]
    assert final["type"] == "_final" and final["text"] == "Réponse finale assemblée."
    assert final["orchestra"]["difficulty"] == "difficile" and len(final["orchestra"]["steps"]) == 2
    assert [r["role"] for r in record] == ["Chef d'orchestre", "1. Redaction", "2. Redaction", "Assemblage"]
    # contexte court : l'étape b reçoit le résultat de a
    assert any("[a] liste" in u for _, _, u in calls)
    assert orchestrator.stats()["runs"] >= 1


def test_route_preview_and_run(client):
    r = client.post("/api/workshop/preview", json={"message": "Bonjour", "pattern": "orchestra"}).json()
    assert r["pattern"] == "orchestra" and r["difficulty"] == "simple" and r["calls"] == 1
    long = "Cherche les prix, puis compare-les, ensuite rédige une synthèse et enfin vérifie les calculs"
    assert client.post("/api/workshop/preview", json={"message": long}).json()["suggested"] == "orchestra"
    with client.stream("POST", "/api/workshop/run", json={"message": "Bonjour", "pattern": "orchestra"}) as resp:
        events = [json.loads(line) for line in resp.iter_lines() if line]
    kinds = [e["type"] for e in events]
    assert "plan" in kinds and kinds[-1] == "done", events[-3:]
    msgs = client.get(f"/api/conversations/{events[0]['conversation_id']}/messages").json()["messages"]
    meta = msgs[-1].get("meta") or {}
    assert meta.get("orchestra", {}).get("difficulty") == "simple"
    s = client.get("/api/orchestra/stats").json()
    assert s["runs"] >= 1 and set(s["failures"]) >= {"format", "verification", "outil"}


def test_engines_without_local(monkeypatch):
    """Comparaison de fournisseurs distants : le local n'apparaît dans aucun rôle, l'exécutant imposé est respecté."""
    from app import orchestrator, workshop
    monkeypatch.setattr(workshop, "candidates", lambda: ["p:fort", "p:moyen", "p:faible", "local"])
    fam = {"p:fort": "gpt", "p:moyen": "llama", "p:faible": "qwen", "local": "qwen"}
    monkeypatch.setattr(workshop, "_info", lambda e: (2, fam[e]))
    e = orchestrator.engines("p:faible", allow_local=False)
    roles = [e["worker"], e["planner"], e["judge"], *e["ladder"]]
    assert "local" not in roles and e["worker"] == "p:faible" and e["ladder"] == ["p:faible", "p:moyen", "p:fort"]
    assert e["judge"] != "p:faible" and not e["same_family_judge"]
    assert orchestrator.engines(allow_local=False)["worker"] == "p:faible"     # le plus faible distant par défaut
    assert orchestrator.engines()["worker"] == "local"


def test_gen_refuses_local_fallback():
    from app import providers, workshop

    async def go():
        return [t async for t in workshop._gen("local", [{"role": "user", "content": "x"}], lambda *a: None, allow_local=False)]
    with pytest.raises(providers.Unavailable):
        run(go())


def test_bench_ask(client):
    r = client.post("/api/bench/ask", json={"message": "Bonjour", "engine": "local"})
    assert r.status_code == 200 and r.json()["answer"] and "seconds" in r.json()
    assert client.post("/api/bench/ask", json={"message": "x", "engine": "p:inexistant"}).status_code == 404
    assert client.post("/api/bench/ask", json={"message": "x", "engine": "rm -rf"}).status_code == 422


def test_unavailable_judge_and_planner_do_not_abort(client, monkeypatch):
    """Un juge, un chef ou un exécutant en panne ne fait plus échouer toute l'orchestration."""
    from app import orchestrator, providers
    monkeypatch.setattr(orchestrator, "SAMPLES", 1)

    def replies(engine, sys, user):
        if engine == "p:panne":
            raise providers.Unavailable("le modèle n'existe pas")
        return "Réponse correcte"
    _fake(monkeypatch, replies)
    eng = {"worker": "p:panne", "planner": "p:panne", "judge": "p:panne", "ladder": ["p:panne", "p:ok"], "same_family_judge": False}
    trace = {"calls": 0, "attempts": 0, "failures": [], "verified": "", "escalated": False}
    step = orchestrator.parse_plan("", "Explique la photosynthèse")[0]
    text, used = run(orchestrator.run_step(step, "Explique", "", eng, "moyenne", trace))
    assert text == "Réponse correcte" and used == "p:ok" and trace["escalated"]
    assert trace["verified"].startswith("format")
