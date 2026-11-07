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

import json
import re
from typing import AsyncIterator

from . import db, hybrid, llm, providers
from .config import DEFAULT_MODEL

DEFAULTS = {
    "enabled": False,
    "pattern": "review",
    "participants": ["auto", "auto", "auto"],      # rôles selon le schéma (voir ROLES) : auto | local | p:<id>
    "rounds": 1,                                   # tours de relecture (review)
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


async def _gen(engine: str, messages: list[dict], on_engine) -> AsyncIterator[str]:
    """Jetons du participant ; s'il est indisponible, relais vers un autre fournisseur puis le local."""
    if engine.startswith("p:"):
        order = providers.chain(engine[2:])
        used: dict = {}
        try:
            async for t in providers.stream_chain(order, messages, used):
                yield t
            if used.get("id") and f"p:{used['id']}" != engine:
                on_engine(f"p:{used['id']}", used.get("skipped") or [])
            return
        except providers.Unavailable as e:
            on_engine("local", [str(e)])
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


def review_ok(text: str) -> bool:
    t = text.lower()
    return bool(re.search(r"verdict\s*:\s*ok\b", t)) and "[bloquant" not in t and "[important" not in t


def _prompts(pattern: str, step: int, request: str, prev: list[str]) -> list[dict]:
    """Messages pour l'étape `step` du schéma, à partir des sorties précédentes."""
    if pattern == "review":
        if step == 0:
            sys = BASE + " Ton rôle : RÉDACTEUR. Produis la meilleure réponse complète possible."
            user = request
        elif step % 2 == 1:
            sys = BASE + REVIEW_GRID
            user = f"Demande :\n{request}\n\nRéponse à relire :\n{prev[-1]}"
        else:
            sys = BASE + (" Ton rôle : RÉDACTEUR. Réécris ta réponse en corrigeant tous les points [bloquant] et "
                          "[important] de la relecture (et les [mineur] si c'est simple). Pour chaque affirmation listée "
                          "comme « non vérifiable », retire-la ou signale clairement l'incertitude. "
                          "Donne uniquement la version finale, sans parler de la relecture.")
            user = f"Demande :\n{request}\n\nTa première version :\n{prev[-2]}\n\nRelecture :\n{prev[-1]}"
    elif pattern == "panel":
        if step < 2:
            sys = BASE + " Propose ta meilleure réponse, de façon indépendante."
            user = request
        else:
            sys = BASE + (" Ton rôle : ARBITRE. Compare les propositions point par point : là où elles divergent, "
                          "détermine laquelle est juste et pourquoi ; là où aucune n'est sûre, dis-le. Garde ce qui est juste "
                          "et utile dans chacune, corrige ce qui est faux, et rédige la réponse finale. "
                          "Donne uniquement la réponse finale (avec, si besoin, une courte mention des incertitudes restantes).")
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
              participants: list[str] | None = None, title: str = "") -> AsyncIterator[dict]:
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

    steps = plan(pattern, participants, s["rounds"])
    outputs: list[str] = []
    record = []
    try:
        i = 0
        while i < len(steps):
            role, engine = steps[i]
            final = i == len(steps) - 1
            # Relecture favorable : inutile de corriger, la première version devient la réponse finale.
            if pattern == "review" and role == "Correction" and outputs and review_ok(outputs[-1]):
                draft = outputs[-2]
                yield dict(type="step", status="start", index=i, role="Validée", engine="relecture favorable", final=final)
                if final:
                    for piece in re.findall(r"\S+\s*|\s+", draft):
                        yield dict(type="token", text=piece)
                outputs.append(draft)
                record.append({"role": "Validée", "engine": "relecture favorable", "text": draft})
                yield dict(type="step", status="done", index=i, text=draft)
                i += 1
                continue
            switched: list = []
            yield dict(type="step", status="start", index=i, role=role, engine=engine_label(engine), final=final)
            text, sent = "", 0
            async for tok in _gen(engine, _prompts(pattern, i, request, outputs), lambda e, why: switched.append((e, why))):  # noqa: B023 (consommé dans la même itération)
                text += tok
                # On retient le début le temps d'écarter un éventuel tag d'émotion ou bloc de réflexion.
                if len(text) < 30 and "]" not in text[:25]:
                    continue
                clean = TAG_RE.sub("", THINK_RE.sub("", text))
                piece, sent = clean[sent:], len(clean)
                if piece:
                    yield dict(type="token", text=piece) if final else dict(type="step", status="token", index=i, text=piece)
            clean = TAG_RE.sub("", THINK_RE.sub("", text))
            if clean[sent:]:
                piece = clean[sent:]
                yield dict(type="token", text=piece) if final else dict(type="step", status="token", index=i, text=piece)
            label = engine_label(engine)
            if switched:
                label = f"{engine_label(switched[-1][0])} (relais)"
                yield dict(type="step", status="engine", index=i, engine=label, reason=" ; ".join(switched[-1][1])[:200])
            text = TAG_RE.sub("", THINK_RE.sub("", text)).strip()
            outputs.append(text)
            record.append({"role": role, "engine": label, "text": text})
            yield dict(type="step", status="done", index=i, text=text)
            i += 1
        final_text = outputs[-1] if outputs else "…"
        meta = {"workshop": {"pattern": pattern, "name": PATTERNS[pattern], "steps": record[:-1]}}
        asst_id = db.add_message(conversation_id, "assistant", final_text, "focus", meta=meta)
        yield dict(type="done", emotion="focus", id=asst_id, final=final_text)
    except Exception as e:  # noqa: BLE001
        yield dict(type="error", message=f"Atelier interrompu : {e}")
