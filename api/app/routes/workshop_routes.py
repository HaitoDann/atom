"""Routes : atelier multi-IA."""
from __future__ import annotations


from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .. import orchestrator, providers, workshop
from ..config import MAX_TOKENS_LONG

router = APIRouter()


from ..streaming import event  # noqa: E402



class WorkshopIn(BaseModel):
    enabled: bool | None = None
    architect: str | None = Field(default=None, pattern="^(auto|on|off)$")
    pattern: str | None = Field(default=None, pattern="^(review|panel|debate|orchestra)$")
    participants: list[str] | None = Field(default=None, max_length=3)
    rounds: int | None = Field(default=None, ge=1, le=3)


class WorkshopRunIn(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: int | None = None
    pattern: str | None = Field(default=None, pattern="^(review|panel|debate|orchestra)$")
    participants: list[str] | None = Field(default=None, max_length=3)
    rounds: int | None = Field(default=None, ge=1, le=3)
    architect: str | None = Field(default=None, pattern="^(auto|on|off)$")
    allow_local: bool = True


class AskIn(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    engine: str = Field(pattern=r"^(local|p:[a-z0-9_-]{1,40})$")


class WorkshopPreviewIn(BaseModel):
    message: str = Field(default="", max_length=8000)
    pattern: str | None = Field(default=None, pattern="^(review|panel|debate|orchestra)$")
    participants: list[str] | None = Field(default=None, max_length=3)
    rounds: int | None = Field(default=None, ge=1, le=3)
    architect: str | None = Field(default=None, pattern="^(auto|on|off)$")


EXAMPLES = [
    {"pattern": "debate", "title": "Une décision",
     "text": "Faut-il héberger mes services à la maison sur Proxmox ou passer sur un VPS chez un hébergeur ? "
             "Je veux de la fiabilité, un coût raisonnable et garder la maîtrise de mes données."},
    {"pattern": "panel", "title": "Une comparaison",
     "text": "Compare SQLite, PostgreSQL et DuckDB pour un assistant personnel qui stocke des conversations, "
             "des souvenirs vectorisés et des statistiques. Donne un tableau et une recommandation argumentée."},
    {"pattern": "review", "title": "Du code à produire",
     "text": "Écris une fonction Python robuste qui découpe un texte long en morceaux d'environ 1 000 caractères "
             "sans couper les phrases, avec des tests pytest pour les cas limites."},
    {"pattern": "review", "title": "Un texte soigné",
     "text": "Rédige un guide clair (une page) pour expliquer à un débutant comment sauvegarder ses photos "
             "selon la règle 3-2-1, avec des exemples concrets et peu coûteux."},
    {"pattern": "orchestra", "title": "Une tâche en plusieurs étapes",
     "text": "Je place 15 000 € à 3,2 % d'intérêts composés par an. Calcule d'abord le capital après 10 ans, "
             "puis compare avec un livret à 2,4 %, ensuite rédige une synthèse claire avec les deux montants "
             "et la différence, et enfin donne trois conseils prudents."},
]


@router.post("/api/workshop/preview")
def preview_workshop(body: WorkshopPreviewIn):
    """L'équipe et les étapes que lancerait l'atelier, sans rien envoyer (lanceur)."""
    return {**workshop.preview(body.pattern, body.participants, body.rounds, body.message, body.architect), "examples": EXAMPLES}


@router.get("/api/workshop")
def get_workshop():
    s = workshop.settings()
    opts = [{"id": "auto", "label": "Automatique"}, {"id": "local", "label": workshop.engine_label("local")}]
    opts += [{"id": f"p:{p.id}", "label": workshop.engine_label(f"p:{p.id}"), "family": providers.family_of(providers.model_of(p), p.family),
              "strength": p.strength} for p in providers.ALL if p.configured]
    assigned = workshop.assign(s["pattern"], s["participants"])
    return {**s, "patterns": workshop.PATTERNS, "roles": workshop.ROLES, "options": opts,
            "assigned": [workshop.engine_label(x) for x in assigned], "warnings": workshop.warnings(s["pattern"], s["participants"])}


@router.put("/api/workshop")
def put_workshop(body: WorkshopIn):
    workshop.save_settings({k: v for k, v in body.model_dump().items() if v is not None})
    return get_workshop()


@router.post("/api/workshop/run")
async def run_workshop(body: WorkshopRunIn):
    # Lancé explicitement (lanceur ou bouton) : pas besoin d'activer l'atelier dans les réglages.
    return StreamingResponse(
        (event(**ev) async for ev in workshop.run(body.message.strip(), body.conversation_id, body.pattern, body.participants,
                                                  rounds=body.rounds, architect=body.architect, allow_local=body.allow_local)),
        media_type="application/x-ndjson")


@router.get("/api/orchestra/stats")
def orchestra_stats():
    """Échecs cumulés par famille et types de vérification (orchestration de petits modèles)."""
    e = orchestrator.engines()
    return {**orchestrator.stats(), "worker": workshop.engine_label(e["worker"]), "planner": workshop.engine_label(e["planner"]),
            "judge": workshop.engine_label(e["judge"]), "ladder": [workshop.engine_label(x) for x in e["ladder"]],
            "same_family_judge": e["same_family_judge"]}


@router.post("/api/bench/ask")
async def bench_ask(body: AskIn):
    """Un seul appel à un moteur précis, sans relais vers un autre fournisseur ni vers le local (banc d'essai)."""
    import time as _t
    if body.engine.startswith("p:") and not (providers.get(body.engine[2:]) and providers.get(body.engine[2:]).configured):
        raise HTTPException(404, f"Fournisseur inconnu ou non configuré : {body.engine[2:]}")
    msgs = [{"role": "system", "content": "Réponds en français, directement, sans émotion entre crochets. /no_think"},
            {"role": "user", "content": body.message}]
    t0, out = _t.time(), ""
    try:
        if body.engine == "local":
            from .. import llm
            async for tok in llm.stream_chat(workshop._local_model(), msgs, task="banc"):
                out += tok
        else:
            async for tok in providers.stream_complete([providers.get(body.engine[2:])], msgs, {},
                                                       max_tokens=MAX_TOKENS_LONG, task="banc"):
                out += tok
    except providers.Unavailable as e:
        raise HTTPException(503, f"{body.engine} indisponible : {e}") from e
    text = workshop.TAG_RE.sub("", workshop.THINK_RE.sub("", out)).strip()
    return {"answer": text, "engine": workshop.engine_label(body.engine), "seconds": round(_t.time() - t0, 1)}
