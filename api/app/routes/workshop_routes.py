"""Routes : atelier multi-IA."""
from __future__ import annotations


from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .. import providers, workshop

router = APIRouter()


from ..streaming import event  # noqa: E402



class WorkshopIn(BaseModel):
    enabled: bool | None = None
    architect: str | None = Field(default=None, pattern="^(auto|on|off)$")
    pattern: str | None = Field(default=None, pattern="^(review|panel|debate)$")
    participants: list[str] | None = Field(default=None, max_length=3)
    rounds: int | None = Field(default=None, ge=1, le=3)


class WorkshopRunIn(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: int | None = None
    pattern: str | None = Field(default=None, pattern="^(review|panel|debate)$")
    participants: list[str] | None = Field(default=None, max_length=3)
    rounds: int | None = Field(default=None, ge=1, le=3)
    architect: str | None = Field(default=None, pattern="^(auto|on|off)$")


class WorkshopPreviewIn(BaseModel):
    message: str = Field(default="", max_length=8000)
    pattern: str | None = Field(default=None, pattern="^(review|panel|debate)$")
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
                                                  rounds=body.rounds, architect=body.architect)),
        media_type="application/x-ndjson")
