# Atom

Assistant IA auto-hébergé : une interface web minimaliste avec un avatar vivant, une sphère de ~3 200 fragments qui se désassemble quand Atom réfléchit et se reconstitue avec l'émotion de sa réponse.

```
Navigateur (PC) ──réseau local──▶ VM/LXC Proxmox : Docker Compose
                                   ├─ atom    : FastAPI, port 8000 (sert l'interface + API)
                                   │    └─ SQLite (historique, souvenirs) dans le volume atom-data
                                   └─ ollama  : qwen3:4b-instruct-2507 (sans mode réflexion), sur CPU
```

## Arborescence

| Chemin | Rôle |
|---|---|
| `web/index.html` | L'interface (un seul fichier, sans build) |
| `api/app/main.py` | Le backend : relais Ollama en streaming, historique, souvenirs |
| `docker-compose.yml` | Ollama + téléchargement du modèle + backend |

## Premier essai sur Proxmox (réseau local)

### 1. Créer la machine

Une **VM Debian 12** est le plus simple pour Docker. Comme le modèle tourne sur CPU, prévois :
- **4 cœurs ou plus** (type de CPU `host`, pour profiter des instructions AVX) ;
- **8 Go de RAM** (le modèle en occupe environ 3 à 4) ;
- **20 Go de disque**.

Un LXC fonctionne aussi, à condition de cocher les options *nesting* et *keyctl* pour Docker.

### 2. Installer Docker dans la VM

```bash
curl -fsSL https://get.docker.com | sudo sh
```

### 3. Récupérer et lancer Atom

```bash
git clone -b claude/new-session-q4ozge https://github.com/HaitoDann/atom.git
```

```bash
cd atom && cp .env.example .env
```

```bash
sudo docker compose up -d --build
```

Le premier lancement télécharge `qwen3:4b-instruct-2507-q4_K_M` (environ 2,5 Go). Pour suivre le téléchargement :

```bash
sudo docker compose logs -f ollama-pull
```

### 4. Ouvrir l'interface

Depuis ton PC : `http://<IP-de-la-VM>:8000`. Pour trouver l'IP, lance `ip -4 a` dans la VM.

La pastille en haut à droite passe au **vert** quand le backend joint Ollama.

### Tester l'interface sans modèle

Pour vérifier toute la chaîne avant de télécharger le modèle, mets `ATOM_PROVIDER=mock` dans `.env`, puis :

```bash
sudo docker compose up -d --build atom
```

Atom répète alors ton message, mot par mot, avec une émotion au hasard.

## Comportement de l'agent

- Atom répond en **une à trois phrases courtes**, avec un modèle local uniquement.
- Les réponses arrivent **en streaming**, et la sphère pulse légèrement à chaque token.
- Le modèle commence sa réponse par un tag d'émotion, par exemple `[joy] Salut !`. Le backend le retire et pilote la sphère avec ; sans tag, l'émotion par défaut est `talking`.
- **L'historique et les souvenirs sont stockés sur le serveur**, en SQLite : on retrouve la conversation depuis n'importe quel navigateur. Les 20 derniers échanges sont envoyés au modèle.
- La personnalité et le choix du modèle restent propres à chaque navigateur.

## Développement sans Docker

```bash
pip install -r api/requirements.txt
```

```bash
cd api && OLLAMA_URL=http://localhost:11434 uvicorn app.main:app --reload --port 8000
```

## API

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/api/health` | État du backend et d'Ollama |
| GET | `/api/models` | Modèles installés |
| POST | `/api/chat` | `{message, model?, persona?}` → flux NDJSON : `emotion`, `token`…, `done` ou `error` |
| GET / DELETE | `/api/history` | Lire ou effacer l'historique |
| GET / PUT | `/api/memories` | Lire ou remplacer les souvenirs |

## Feuille de route

1. ✅ Backend + Docker Compose + streaming
2. Mémoire automatique : extraction de faits, recherche dans les anciennes conversations (`sqlite-vec` + `nomic-embed-text`), panneau de contrôle
3. Documents : import de notes et de PDF, puis recherche dedans
4. Accès distant via Tailscale ; plus tard, API externes en secours et voix
