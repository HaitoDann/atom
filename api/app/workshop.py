"""Atelier multi-IA : plusieurs modèles travaillent ensemble sur une demande importante.

Schémas :
- « review »  : un rédacteur écrit, un relecteur critique, le rédacteur corrige.
- « panel »   : plusieurs participants proposent chacun une réponse, un arbitre fait la synthèse.
- « debate »  : deux participants défendent des positions opposées, un arbitre tranche.

Participants : « auto » (Atom répartit les rôles), « local » (Ollama) ou « p:<fournisseur> ».
Répartition auto : le plus fort rédige, un modèle d'une autre famille relit, l'arbitre n'est jamais le plus faible.
Relais : un participant indisponible (limite, panne) est remplacé par le suivant, puis par le local.
Confidentialité : l'atelier ne reçoit que ta demande et le fil récent de la conversation —
ni souvenirs, ni bibliothèque, ni fichiers.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from typing import AsyncIterator

from . import db, hybrid, llm, providers
from .config import DEFAULT_MODEL, MAX_TOKENS_LONG
import logging

log = logging.getLogger("atom.workshop")

DEFAULTS = {
    "enabled": False,
    "pattern": "review",
    "participants": ["auto", "auto", "auto"],      # rôles selon le schéma (voir ROLES) : auto | local | p:<id>
    "rounds": 1,                                   # tours de relecture (review)
    "architect": "auto",                           # architecte en premier : auto (livrables) | on | off
}

ROLES = {
    "review": ["Rédacteur", "Relecteur", "Correction"],
    "panel": ["Proposition A", "Proposition B", "Arbitre"],
    "debate": ["Pour", "Contre", "Arbitre"],
}
PATTERNS = {
    "review": "Rédaction puis relecture",
    "panel": "Comité et arbitre",
    "debate": "Débat contradictoire",
}

TAG_RE = re.compile(r"^\s*\[[a-zA-Z]+\]\s*")
THINK_RE = re.compile(r"<think>[\s\S]*?</think>")


def settings() -> dict:
    s = dict(DEFAULTS)
    raw = db.kv_get("workshop")
    if raw:
        try:
            s.update({k: v for k, v in json.loads(raw).items() if k in DEFAULTS})
        except ValueError:
            pass
    return s


def save_settings(new: dict) -> dict:
    s = settings()
    if "participants" in new:
        new["participants"] = [x if x in ("auto", "local") or (x.startswith("p:") and providers.get(x[2:])) or x.startswith("remote")
                               else "auto" for x in new["participants"] if isinstance(x, str)]
    s.update({k: v for k, v in new.items() if k in DEFAULTS})
    if s["pattern"] not in ROLES:
        s["pattern"] = "review"
    s["participants"] = [p for p in s["participants"] if isinstance(p, str)][:3] or ["local"] * 3
    while len(s["participants"]) < 3:
        s["participants"].append(s["participants"][-1])
    s["rounds"] = max(1, min(3, int(s.get("rounds", 1))))
    if s.get("architect") not in ("auto", "on", "off"):
        s["architect"] = "auto"
    db.kv_set("workshop", json.dumps(s))
    return s


# ---------------------------------------------------------------- participants
# « local », « p:<id> » (un fournisseur), « auto » (Atom choisit), ou l'ancien « remote[:modèle] ».


def _local_model() -> str:
    return db.kv_get("model") or DEFAULT_MODEL


def _norm(engine: str) -> str:
    if engine.startswith("remote"):
        p = hybrid.primary()
        return f"p:{p.id}" if p else "local"
    return engine


def _info(engine: str) -> tuple[int, str]:
    """(force, famille) d'un participant concret."""
    if engine.startswith("p:"):
        p = providers.get(engine[2:])
        if p:
            return p.strength, providers.family_of(providers.model_of(p), p.family)
    return providers.LOCAL_STRENGTH, providers.family_of(_local_model(), "local")


def candidates() -> list[str]:
    """Participants concrets disponibles, du plus fort au plus faible (le local toujours en dernier recours)."""
    pool = [f"p:{p.id}" for p in providers.chain()]   # l'atelier n'envoie aucune donnée privée
    return pool + ["local"]


def assign(pattern: str, participants: list[str]) -> list[str]:
    """Remplace les « auto » : rédacteur = le plus fort ; relecteur = une autre famille ;
    arbitre = jamais le plus faible (le plus fort disponible, si possible un troisième)."""
    slots = [_norm(x) for x in (participants + ["auto"] * 3)[:3]]
    cands = candidates()
    strongest = cands[0]

    def pick(avoid: set[str], avoid_family: str | None = None) -> str:
        for c in cands:
            if c not in avoid and (avoid_family is None or _info(c)[1] != avoid_family):
                return c
        for c in cands:
            if c not in avoid:
                return c
        return strongest

    if slots[0] == "auto":
        slots[0] = strongest
    if slots[1] == "auto":
        slots[1] = pick({slots[0]}, _info(slots[0])[1])
    if slots[2] == "auto":
        if pattern == "review":
            slots[2] = slots[0]            # la correction revient au rédacteur
        else:
            top = _info(strongest)[0]
            third = [c for c in cands if c not in slots[:2] and _info(c)[0] >= top]
            slots[2] = third[0] if third else strongest
    return slots


def warnings(pattern: str, participants: list[str]) -> list[str]:
    """Conseils quand un choix manuel affaiblit l'atelier."""
    s = assign(pattern, participants)
    out = []
    if _info(s[0])[1] == _info(s[1])[1] and len(candidates()) > 1:
        out.append("Le relecteur est de la même famille que le rédacteur : ils risquent de faire les mêmes erreurs.")
    best = max(_info(c)[0] for c in candidates())
    judge = s[2]
    if pattern != "review" and _info(judge)[0] < best:
        out.append("L'arbitre n'est pas le modèle le plus fort disponible : il risque de mal trancher.")
    return out


def engine_label(engine: str) -> str:
    if engine.startswith("p:"):
        p = providers.get(engine[2:])
        if p:
            return f"{p.name} · {providers.model_of(p)}"
    return f"Local · {_local_model().split(':')[0]}"


RETRY_WAIT = float(os.getenv("ATOM_WORKSHOP_RETRY_WAIT", "45"))


async def _gen(engine: str, messages: list[dict], on_engine) -> AsyncIterator[str]:
    """Jetons du participant ; s'il est indisponible, relais vers un autre fournisseur, puis — si tous sont seulement
    en pause pour quelques secondes (limite par minute) — attente et nouvel essai, et le local en dernier recours :
    un petit modèle local relit mal du code et prend plusieurs minutes."""
    if engine.startswith("p:"):
        last = ""
        for attempt in range(2):
            order = providers.chain(engine[2:])
            used: dict = {}
            got = False
            try:
                # Budget long et reprise automatique : une page web ou un fichier complet n'est plus coupé en route.
                async for t in providers.stream_complete(order, messages, used, max_tokens=MAX_TOKENS_LONG, task="atelier"):
                    got = True
                    yield t
                if used.get("id") and f"p:{used['id']}" != engine:
                    on_engine(f"p:{used['id']}", used.get("skipped") or [])
                return
            except providers.Unavailable as e:
                if got:
                    raise
                last = str(e)
            wait = providers.soonest_resume()
            if attempt or wait is None or wait > RETRY_WAIT:
                break
            log.info("atelier : fournisseurs en pause, nouvel essai dans %.0f s", wait)
            await asyncio.sleep(wait + 1)
        on_engine("local", [last or "aucun fournisseur distant disponible"])
    async for t in llm.stream_chat(_local_model(), messages):
        yield t


BASE = ("Tu participes à un atelier où plusieurs IA collaborent pour aider l'utilisateur. "
        "Réponds en français, directement, sans commencer par une émotion entre crochets, "
        "sans réfléchir à voix haute. /no_think")

REVIEW_GRID = (
    " Ton rôle : RELECTEUR exigeant. Vérifie la réponse ci-dessous selon cette grille, critère par critère :\n"
    "1. Exactitude : faits, chiffres, dates, noms, code (syntaxe, logique, cas limites, sécurité).\n"
    "2. Consignes : chaque point de la demande est-il traité ? Liste ce qui manque.\n"
    "3. Cohérence : contradictions, raisonnement qui ne tient pas, conclusion non justifiée.\n"
    "4. Utilité : trop vague, hors sujet, longueur inadaptée, manque d'exemple concret.\n"
    "Pour chaque problème : une ligne « - [bloquant|important|mineur] critère : problème → correction proposée ».\n"
    "Puis une section « Non vérifiable : » listant les affirmations que tu ne peux pas confirmer "
    "(information récente, chiffre précis, source inconnue) — n'invente pas de vérification.\n"
    "Termine par « Verdict : OK » s'il n'y a rien de bloquant ni d'important, sinon « Verdict : À corriger ». "
    "Ne réécris pas la réponse."
)


# Livrables (code, page web, document) : des consignes précises font toute la différence avec une réponse « simpliste ».
DELIVERABLE_RE = re.compile(r"\b(page web|site( web)?|landing|html|css|javascript|application|script|fonction|programme|"
                            r"composant|api|code)\b|```", re.I)
DELIVERABLE_RULES = (
    " La demande porte sur un LIVRABLE (code, page web, fichier). Exigences :\n"
    "- Commence par 3 à 6 lignes « Choix de conception » (structure, sections, palette, typographie, ton), puis livre.\n"
    "- Livre chaque fichier EN ENTIER dans son propre bloc de code, avec son nom sur la ligne juste avant "
    "(ex. « **index.html** »). Jamais de « … », de « reste inchangé » ni de fichier coupé.\n"
    "- Aucun texte d'exemple (« Nom de votre entreprise », « Lorem ipsum », « votre slogan ici ») : invente un contenu "
    "réaliste et cohérent avec la demande, et signale en une ligne à la fin ce que l'utilisateur doit personnaliser.\n"
    "- Page web : un seul fichier HTML autonome (CSS et JS intégrés) sauf demande contraire ; plusieurs sections riches "
    "(en-tête avec navigation, présentation, services ou produits détaillés, équipe ou valeurs, témoignages, contact, pied "
    "de page) ; responsive (mobile d'abord) ; contrastes lisibles (WCAG AA), y compris les liens de navigation ; états "
    "survol et focus ; respecte précisément le style demandé (couleurs, ambiance, références).\n"
    "- Code : fonctionnel tel quel, gestion des erreurs et des cas limites, commentaires utiles, sans dépendance inutile."
)
DELIVERABLE_GRID = (
    "\n5. Livrable : fichier complet ou coupé ? textes d'exemple restants (« Nom de votre entreprise », « Lorem ») ? "
    "contenu trop pauvre (sections vides, une phrase par section) ? style demandé respecté ? contrastes (texte et liens "
    "lisibles sur leur fond) ? responsive ? le code fonctionne-t-il tel quel ?"
)


def is_deliverable(request: str) -> bool:
    return bool(DELIVERABLE_RE.search(request or ""))


ARCHITECT_PROMPT = (
    " Ton rôle : ARCHITECTE. Tu ne rédiges pas la réponse : tu transformes la demande en cahier des charges précis "
    "que d'autres modèles suivront. Structure : 1) Objectif et public ; 2) Contenu attendu, partie par partie (pour une "
    "page web : chaque section avec son contenu réel à écrire — textes, exemples, chiffres plausibles) ; 3) Style "
    "(palette avec codes couleur, typographie, ambiance, références citées par l'utilisateur) ; 4) Exigences techniques "
    "(fichiers à livrer, responsive, accessibilité, contraintes) ; 5) Critères de réussite vérifiables. Comble les "
    "manques par des choix raisonnables et dis-le en une ligne. Sois concret et concis (40 lignes au plus)."
)


def wants_architect(mode: str, request: str) -> bool:
    return mode == "on" or (mode == "auto" and is_deliverable(request))


def review_ok(text: str) -> bool:
    t = text.lower()
    return bool(re.search(r"verdict\s*:\s*ok\b", t)) and "[bloquant" not in t and "[important" not in t


def _prompts(pattern: str, step: int, request: str, prev: list[str]) -> list[dict]:
    """Messages pour l'étape `step` du schéma, à partir des sorties précédentes."""
    deliv = is_deliverable(request)
    rules = DELIVERABLE_RULES if deliv else ""
    if pattern == "review":
        if step == 0:
            sys = BASE + " Ton rôle : RÉDACTEUR. Produis la meilleure réponse complète possible." + rules
            user = request
        elif step % 2 == 1:
            sys = BASE + REVIEW_GRID.replace("Termine par", (DELIVERABLE_GRID + "\n") if deliv else "Termine par", 1) \
                + ("Termine par" if deliv else "")
            user = f"Demande :\n{request}\n\nRéponse à relire :\n{prev[-1]}"
        else:
            sys = BASE + (" Ton rôle : RÉDACTEUR. Réécris ta réponse en corrigeant tous les points [bloquant] et "
                          "[important] de la relecture (et les [mineur] si c'est simple). Pour chaque affirmation listée "
                          "comme « non vérifiable », retire-la ou signale clairement l'incertitude. "
                          "Donne uniquement la version finale COMPLÈTE (tous les fichiers en entier), sans parler de la relecture.")
            sys += rules
            user = f"Demande :\n{request}\n\nTa première version :\n{prev[-2]}\n\nRelecture :\n{prev[-1]}"
    elif pattern == "panel":
        if step < 2:
            sys = BASE + " Propose ta meilleure réponse, de façon indépendante." + rules
            user = request
        else:
            sys = BASE + (" Ton rôle : ARBITRE. Compare les propositions point par point : là où elles divergent, "
                          "détermine laquelle est juste et pourquoi ; là où aucune n'est sûre, dis-le. Garde ce qui est juste "
                          "et utile dans chacune, corrige ce qui est faux, et rédige la réponse finale. "
                          "Donne uniquement la réponse finale (avec, si besoin, une courte mention des incertitudes restantes).")
            sys += rules
            user = f"Demande :\n{request}\n\nProposition A :\n{prev[0]}\n\nProposition B :\n{prev[1]}"
    else:  # debate
        if step == 0:
            sys = BASE + " Ton rôle : défendre la réponse « oui » / l'option la plus favorable. Argumente solidement, sans caricaturer."
            user = request
        elif step == 1:
            sys = BASE + " Ton rôle : défendre la position opposée à celle-ci, avec des arguments solides."
            user = f"Question :\n{request}\n\nPosition à contredire :\n{prev[0]}"
        else:
            sys = BASE + (" Ton rôle : ARBITRE impartial. Pèse les arguments des deux positions (repère les arguments "
                          "faux ou non étayés), tranche quand c'est possible, et donne une recommandation claire et nuancée.")
            user = f"Question :\n{request}\n\nPosition 1 :\n{prev[0]}\n\nPosition 2 :\n{prev[1]}"
    return [{"role": "system", "content": sys}, {"role": "user", "content": user}]


DEBATE_RE = re.compile(r"\b(faut-il|dois-je|devrais-je|vaut-il mieux|est-ce une bonne idée|pour ou contre|"
                       r"avantages et inconvénients)\b|\b\w+\s+ou\s+[^?]{1,60}\?", re.I)   # « X ou Y ? » : un choix
PANEL_RE = re.compile(r"\b(compare|comparer|comparatif|analyse|analyser|évalue|évaluer|stratégie|plan d'action|options|"
                      r"meilleure façon|recommande|propose plusieurs)\b", re.I)


def suggest(message: str) -> tuple[str, str]:
    """Schéma conseillé pour une demande, avec la raison (affichée dans le lanceur)."""
    m = message or ""
    if DEBATE_RE.search(m):
        return "debate", "une décision à prendre : deux positions opposées, puis un arbitre tranche"
    if PANEL_RE.search(m):
        return "panel", "une analyse ou une comparaison : deux propositions indépendantes, puis une synthèse"
    return "review", "un texte ou du code à produire : un rédacteur, un relecteur exigeant, puis une version corrigée"


def preview(pattern: str | None, participants: list[str] | None, rounds: int | None, message: str = "",
            architect: str | None = None) -> dict:
    """Ce que ferait l'atelier, sans rien lancer : étapes, modèles, appels distants, conseils."""
    s = settings()
    suggested, why = suggest(message)
    pattern = pattern if pattern in ROLES else s["pattern"]
    participants = participants or s["participants"]
    rounds = max(1, min(3, int(rounds or s["rounds"])))
    steps = plan(pattern, participants, rounds)
    arch_mode = architect if architect in ("auto", "on", "off") else s["architect"]
    if wants_architect(arch_mode, message):
        steps = [("Architecte", candidates()[0])] + steps
    labels = [{"role": r, "engine": engine_label(e), "remote": e.startswith("p:"), "family": _info(e)[1]} for r, e in steps]
    return {"pattern": pattern, "name": PATTERNS[pattern], "rounds": rounds, "participants": participants,
            "suggested": suggested, "suggested_name": PATTERNS[suggested], "suggested_reason": why,
            "steps": labels, "calls": len(steps), "remote_calls": sum(1 for x in labels if x["remote"]),
            "warnings": warnings(pattern, participants) + (
                ["3 tours de relecture : rarement utile et nettement plus long ; 1 tour avec un bon relecteur suffit souvent."]
                if pattern == "review" and rounds >= 3 else []),
            "roles": ROLES[pattern], "architect": arch_mode, "architect_active": steps[0][0] == "Architecte",
            "deliverable": is_deliverable(message)}


def plan(pattern: str, participants: list[str], rounds: int) -> list[tuple[str, str]]:
    """[(rôle, moteur concret)] dans l'ordre d'exécution."""
    p = assign(pattern, participants)
    if pattern == "review":
        steps = [("Rédacteur", p[0])]
        for _ in range(rounds):
            steps += [("Relecteur", p[1]), ("Correction", p[2])]
        return steps
    return [(ROLES[pattern][0], p[0]), (ROLES[pattern][1], p[1]), (ROLES[pattern][2], p[2])]


async def run(message: str, conversation_id: int | None, pattern: str | None = None,
              participants: list[str] | None = None, title: str = "", rounds: int | None = None,
              architect: str | None = None) -> AsyncIterator[dict]:
    """Événements : meta, step (start/token/done), token… (réponse finale), done — ou error."""
    from .agent import make_title

    s = settings()
    pattern = pattern if pattern in ROLES else s["pattern"]
    participants = participants or s["participants"]
    if conversation_id is None or not db.conversation_exists(conversation_id):
        conversation_id = db.create_conversation("Atelier · " + make_title(title or message))
    yield dict(type="meta", conversation_id=conversation_id)

    # Contexte : les derniers échanges, résumés dans la demande (pas de mémoire ni de documents).
    hist = db.messages(conversation_id, 6)
    context = "\n".join(f"{'Utilisateur' if m['role'] == 'user' else 'Atom'} : {m['content'][:600]}" for m in hist)
    request = (f"Contexte de la conversation :\n{context}\n\nDemande actuelle :\n{message}" if context else message)
    user_id = db.add_message(conversation_id, "user", message)
    yield dict(type="ids", user_id=user_id)

    steps = plan(pattern, participants, max(1, min(3, int(rounds or s["rounds"]))))
    arch = ("Architecte", candidates()[0]) if wants_architect(architect or s["architect"], message) else None
    off = 1 if arch else 0
    # Le plan complet d'abord : l'interface affiche toutes les étapes à venir (en attente, en cours, terminée).
    yield dict(type="plan", pattern=pattern, name=PATTERNS[pattern],
               steps=[{"role": r, "engine": engine_label(e), "remote": e.startswith("p:")} for r, e in ([arch] if arch else []) + steps])
    outputs: list[str] = []
    record = []
    try:
        if arch:
            # L'architecte transforme la demande en cahier des charges : tous les autres travaillent à partir de lui.
            t_step, brief, switched = time.time(), "", []
            yield dict(type="step", status="start", index=0, role="Architecte", engine=engine_label(arch[1]), final=False)
            msgs = [{"role": "system", "content": BASE + ARCHITECT_PROMPT}, {"role": "user", "content": request}]
            async for tok in _gen(arch[1], msgs, lambda e, why: switched.append((e, why))):
                brief += tok
                yield dict(type="step", status="token", index=0, text=tok)
            brief = TAG_RE.sub("", THINK_RE.sub("", brief)).strip()
            label = f"{engine_label(switched[-1][0])} (relais)" if switched else engine_label(arch[1])
            record.append({"role": "Architecte", "engine": label, "text": brief, "seconds": round(time.time() - t_step, 1)})
            yield dict(type="step", status="done", index=0, text=brief, seconds=round(time.time() - t_step, 1))
            if brief:
                request = f"{request}\n\nCahier des charges établi par l'architecte (à suivre) :\n{brief}"
        i = 0
        while i < len(steps):
            role, engine = steps[i]
            final = i == len(steps) - 1
            # Relecture favorable : inutile de corriger, la première version devient la réponse finale.
            if pattern == "review" and role == "Correction" and outputs and review_ok(outputs[-1]):
                draft = outputs[-2]
                yield dict(type="step", status="start", index=i + off, role="Validée", engine="relecture favorable", final=final)
                if final:
                    for piece in re.findall(r"\S+\s*|\s+", draft):
                        yield dict(type="token", text=piece)
                outputs.append(draft)
                record.append({"role": "Validée", "engine": "relecture favorable", "text": draft})
                yield dict(type="step", status="done", index=i + off, text=draft)
                i += 1
                continue
            switched: list = []
            t_step = time.time()
            yield dict(type="step", status="start", index=i + off, role=role, engine=engine_label(engine), final=final)
            text, sent = "", 0
            async for tok in _gen(engine, _prompts(pattern, i, request, outputs), lambda e, why: switched.append((e, why))):  # noqa: B023 (consommé dans la même itération)
                text += tok
                # On retient le début le temps d'écarter un éventuel tag d'émotion ou bloc de réflexion.
                if len(text) < 30 and "]" not in text[:25]:
                    continue
                clean = TAG_RE.sub("", THINK_RE.sub("", text))
                piece, sent = clean[sent:], len(clean)
                if piece:
                    yield dict(type="token", text=piece) if final else dict(type="step", status="token", index=i + off, text=piece)
            clean = TAG_RE.sub("", THINK_RE.sub("", text))
            if clean[sent:]:
                piece = clean[sent:]
                yield dict(type="token", text=piece) if final else dict(type="step", status="token", index=i + off, text=piece)
            label = engine_label(engine)
            if switched:
                label = f"{engine_label(switched[-1][0])} (relais)"
                yield dict(type="step", status="engine", index=i + off, engine=label, reason=" ; ".join(switched[-1][1])[:200])
            text = TAG_RE.sub("", THINK_RE.sub("", text)).strip()
            outputs.append(text)
            record.append({"role": role, "engine": label, "text": text, "seconds": round(time.time() - t_step, 1)})
            yield dict(type="step", status="done", index=i + off, text=text, seconds=round(time.time() - t_step, 1))
            i += 1
        final_text = outputs[-1] if outputs else "…"
        last = {k: v for k, v in record[-1].items() if k != "text"} if record else None
        meta = {"workshop": {"pattern": pattern, "name": PATTERNS[pattern], "steps": record[:-1], "final": last}}
        asst_id = db.add_message(conversation_id, "assistant", final_text, "focus", meta=meta)
        yield dict(type="done", emotion="focus", id=asst_id, final=final_text)
    except Exception as e:
        log.warning("workshop : erreur gérée", exc_info=True)
        yield dict(type="error", message=f"Atelier interrompu : {e}")
