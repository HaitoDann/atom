"""Configuration lue dans l'environnement (voir .env.example)."""

import os
from pathlib import Path

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
DEFAULT_MODEL = os.getenv("ATOM_MODEL", "qwen3:4b-instruct-2507-q4_K_M")
EMBED_MODEL = os.getenv("ATOM_EMBED_MODEL", "nomic-embed-text")
PROVIDER = os.getenv("ATOM_PROVIDER", "ollama")  # "ollama" | "mock"
DB_PATH = Path(os.getenv("ATOM_DB", "data/atom.db"))
WEB_DIR = Path(os.getenv("ATOM_WEB", Path(__file__).resolve().parents[2] / "web"))
CONTEXT_TURNS = int(os.getenv("ATOM_CONTEXT_TURNS", "20"))
MAX_TOKENS = int(os.getenv("ATOM_MAX_TOKENS", "1500"))

# Mémoire
FACTS_IN_PROMPT = int(os.getenv("ATOM_FACTS_IN_PROMPT", "8"))
RECALL_IN_PROMPT = int(os.getenv("ATOM_RECALL_IN_PROMPT", "3"))
FACT_MIN_SCORE = float(os.getenv("ATOM_FACT_MIN_SCORE", "0.45"))
RECALL_MIN_SCORE = float(os.getenv("ATOM_RECALL_MIN_SCORE", "0.55"))
DUPLICATE_SCORE = float(os.getenv("ATOM_DUPLICATE_SCORE", "0.9"))

EMOTIONS = ["idle", "thinking", "talking", "joy", "angry", "sad", "surprise", "fear", "sleep", "curious", "focus"]

DEFAULT_PERSONA = (
    "Tu es Atom, une entité numérique bienveillante, curieuse et concise. "
    "Tu parles français avec naturel et chaleur."
)

# Fuseau horaire de l'utilisateur (rappels, date du jour dans le prompt)
TIMEZONE = os.getenv("TZ", "Europe/Paris")

# Notifications ntfy
NTFY_URL = os.getenv("ATOM_NTFY_URL", "").rstrip("/")      # ex. http://ntfy:80 (vide = désactivé)
NTFY_TOPIC = os.getenv("ATOM_NTFY_TOPIC", "atom")
NTFY_TOKEN = os.getenv("ATOM_NTFY_TOKEN", "")               # si le serveur ntfy exige une auth
PUBLIC_URL = os.getenv("ATOM_PUBLIC_URL", "").rstrip("/")   # URL de l'interface, pour le clic sur la notification
SCHEDULER_INTERVAL = float(os.getenv("ATOM_SCHEDULER_INTERVAL", "20"))

# Telegram (bot de discussion bidirectionnel)
TELEGRAM_TOKEN = os.getenv("ATOM_TELEGRAM_TOKEN", "")
# Identifiants Telegram autorisés, séparés par des virgules (les autres sont refusés)
TELEGRAM_ALLOWED = {
    int(x) for x in os.getenv("ATOM_TELEGRAM_ALLOWED", "").replace(" ", "").split(",") if x.isdigit()
}

# Fenêtre de contexte du modèle (tokens). 8192 laisse la place aux fichiers joints.
NUM_CTX = int(os.getenv("ATOM_NUM_CTX", "8192"))
# Taille max d'un fichier joint injecté dans le prompt (caractères)
ATTACH_MAX_CHARS = int(os.getenv("ATOM_ATTACH_MAX_CHARS", "12000"))

# Recherche web (SearXNG auto-hébergé). Vide = désactivée.
SEARXNG_URL = os.getenv("ATOM_SEARXNG_URL", "").rstrip("/")
SEARCH_RESULTS = int(os.getenv("ATOM_SEARCH_RESULTS", "5"))
SEARCH_PAGES = int(os.getenv("ATOM_SEARCH_PAGES", "3"))

# Threads CPU donnés au modèle (0 = laisser Ollama choisir)
NUM_THREADS = int(os.getenv("ATOM_NUM_THREADS", "0"))

# Sauvegardes
BACKUP_DIR = Path(os.getenv("ATOM_BACKUP_DIR", "data/backups"))
BACKUP_KEEP = int(os.getenv("ATOM_BACKUP_KEEP", "7"))
BACKUP_TIME = os.getenv("ATOM_BACKUP_TIME", "03:30")

# Bibliothèque
DATA_DIR = DB_PATH.parent
PROJECTS_DIR = Path(os.getenv("ATOM_PROJECTS_DIR", "/projects"))   # dossiers de code du serveur (lecture seule)
GITHUB_TOKEN = os.getenv("ATOM_GITHUB_TOKEN", "")                    # pour les dépôts privés
