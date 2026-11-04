# Atom

Assistant IA auto-hébergé : une interface web minimaliste avec un avatar vivant, une sphère de ~3 200 fragments qui se désassemble quand Atom réfléchit et se reconstitue avec l'émotion de sa réponse.

```
Navigateur (PC) ──réseau local──▶ VM/LXC Proxmox : Docker Compose
                                   ├─ atom    : FastAPI, port 8000 (sert l'interface + API)
                                   │    └─ SQLite (conversations, souvenirs, index de rappel) — volume atom-data
                                   ├─ ollama  : qwen3:4b-instruct-2507 (chat) + nomic-embed-text (mémoire), sur CPU
                                   └─ ntfy    : notifications push vers le téléphone, port 8080
```

## Arborescence

| Chemin | Rôle |
|---|---|
| `web/index.html` | L'interface (un seul fichier, sans build) |
| `api/app/main.py` | Routes HTTP et boucle de chat en streaming |
| `api/app/memory.py` | Mémoire automatique : extraction de faits, rappel sémantique |
| `api/app/llm.py` | Accès à Ollama : chat, JSON contraint, embeddings |
| `api/app/reminders.py` | Rappels : commandes du modèle, planificateur |
| `api/app/agent.py` | Cœur de l'agent : prompt, streaming, commandes (partagé web / Telegram) |
| `api/app/telegram.py` | Bot Telegram bidirectionnel |
| `api/app/notify.py` | Canaux sortants (ntfy, Telegram) |
| `api/app/db.py` | Stockage SQLite et migrations |
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

## Interface

- **Barre latérale** : conversations groupées par date, épinglage, renommage (double-clic), recherche dans tout l'historique (`Ctrl+K`), nouvelle conversation (`Ctrl+Maj+O`).
- **Messages** : copier, modifier un message envoyé (`↑` pour le dernier), régénérer la dernière réponse, bouton Stop pendant la génération, copie des blocs de code, export de la conversation en Markdown.
- **Panneau de l'entité** (à droite) : la sphère, son émotion, l'état du serveur (CPU, RAM, modèle chargé, vitesse en tokens/s), les prochains rappels et les derniers souvenirs. Repliable ; en tiroir sur écran étroit.
- **Boutons rapides** sous la saisie et suggestions à l'ouverture d'une conversation vide.
- Thème monochrome : la seule couleur vient de l'émotion de l'entité.

## Mémoire

Atom retient seul ce qui compte, et tu gardes la main.

- **Faits sur toi** : après chaque réponse, le modèle relit l'échange en arrière-plan et en extrait les informations durables (« L'utilisateur a un serveur Proxmox »). Un bandeau « Atom a retenu… » s'affiche quand il apprend quelque chose. Les doublons sont écartés par similarité sémantique.
- **Anciennes conversations** : chaque échange est indexé (`nomic-embed-text`). Quand tu écris, les passages les plus proches tirés d'*autres* conversations sont rappelés au modèle.
- **Injection ciblée** : seuls les faits pertinents pour ton message sont ajoutés au prompt, pas toute la mémoire.
- **Contrôle** : puce en bas à droite → « Ce qu'Atom sait de toi ». Chaque souvenir est marqué `auto` ou `moi`, modifiable et supprimable ; la mémoire automatique se coupe d'une case à cocher ; « Tout oublier » efface tout.

Sans `nomic-embed-text`, la mémoire fonctionne quand même en mode simple (faits les plus récents, pas de rappel des anciennes conversations).

## Rappels et notifications

Demande simplement : « Rappelle-moi demain à 9 h d'appeler le garage ». Atom confirme, le rappel apparaît dans les réglages (puce en bas à droite → Rappels), et à l'heure dite :
- une **notification** arrive sur ton téléphone via ntfy ; un clic ouvre Atom sur la bonne conversation ;
- le rappel s'ajoute aussi dans la conversation.

Atom connaît la date et l'heure, et la liste des rappels programmés : « Quels sont mes rappels ? » ou « Annule le rappel du garage » fonctionnent.

### Configurer ntfy

1. Dans `.env` (voir `.env.example`), remplace l'IP par celle de ta VM et choisis un sujet difficile à deviner :

   ```
   ATOM_PUBLIC_URL=http://192.168.1.28:8000
   NTFY_BASE_URL=http://192.168.1.28:8080
   ATOM_NTFY_TOPIC=atom-un-nom-secret
   ```

2. Relance : `docker compose up -d --build`.
3. Sur le téléphone, installe l'appli **ntfy** (Android ou iOS), puis : **＋ → S'abonner à un sujet → Utiliser un autre serveur** : `http://192.168.1.28:8080`, sujet : celui de `ATOM_NTFY_TOPIC`.
4. Dans Atom : réglages → **Tester la notification**.

> **Android** : dans l'appli ntfy, autorise-la à fonctionner en arrière-plan (désactive l'optimisation de batterie pour elle).
> **iPhone** : iOS n'autorise le push instantané que via les serveurs d'Apple. Décommente `NTFY_UPSTREAM_BASE_URL=https://ntfy.sh` : ton serveur envoie alors seulement un signal anonyme à ntfy.sh (pas le contenu), qui réveille l'appli.
> Pour l'instant, les notifications n'arrivent que quand le téléphone est sur ton réseau local ; ce sera réglé avec l'accès distant (Tailscale).

## Telegram

Discute avec Atom depuis n'importe où, sans Tailscale ni port ouvert : c'est Atom qui va chercher tes messages chez Telegram.

1. Dans Telegram, ouvre **@BotFather** → `/newbot` → choisis un nom (ex. « Atom ») et un identifiant (ex. `atom_haito_bot`). Copie le **jeton** qu'il te donne.
2. Dans `.env` : `ATOM_TELEGRAM_TOKEN=<le jeton>`, puis `docker compose up -d atom`.
3. Écris à ton bot : il te répond avec **ton identifiant Telegram**. Mets-le dans `.env` : `ATOM_TELEGRAM_ALLOWED=<ton identifiant>`, puis relance `docker compose up -d atom`.
4. Écris-lui à nouveau : c'est Atom qui répond. 🎉

Comportement :
- la réponse s'écrit progressivement, puis s'affiche mise en forme (gras, listes, code ; les tableaux sont alignés en police fixe) ;
- l'émotion d'Atom s'affiche en **réaction** sur ton message (😁 🤔 😢 🤯…) ;
- les rappels arrivent directement dans la discussion (en plus de ntfy s'il est configuré) ;
- `/nouveau` démarre une nouvelle conversation, `/rappels` liste les rappels, `/souvenirs` montre ce qu'Atom sait de toi ;
- les conversations Telegram apparaissent aussi dans l'interface web (préfixe ✈), avec la même mémoire ;
- Atom utilise la personnalité et le modèle choisis en dernier dans l'interface web.

> Sécurité : seuls les identifiants de `ATOM_TELEGRAM_ALLOWED` sont servis ; garde le jeton secret (quiconque l'a peut piloter le bot). Les messages transitent par Telegram ; le modèle et la mémoire restent chez toi.

## Comportement de l'agent

- Atom **adapte la longueur** : court pour discuter, complet et structuré en Markdown (titres, listes, tableaux, code) pour une demande de travail.
- **Plusieurs conversations** : bouton ☰ en haut à gauche pour la liste, ＋ pour en commencer une nouvelle.
- Les réponses arrivent **en streaming**, et la sphère pulse légèrement à chaque token.
- Le modèle commence sa réponse par un tag d'émotion, par exemple `[joy] Salut !`. Le backend le retire et pilote la sphère avec ; sans tag, l'émotion par défaut est `talking`.
- **Tout est stocké sur le serveur**, en SQLite : on retrouve ses conversations depuis n'importe quel navigateur. Les 20 derniers échanges de la conversation courante sont envoyés au modèle.
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
| POST | `/api/chat` | `{message, conversation_id?, model?, persona?, auto_memory?}` → flux NDJSON : `meta`, `emotion`, `token`…, `done`, puis `memory` ; ou `error` |
| GET | `/api/conversations` | Liste des conversations |
| GET | `/api/conversations/{id}/messages` | Messages d'une conversation |
| PATCH / DELETE | `/api/conversations/{id}` | Renommer / supprimer |
| GET / POST / DELETE | `/api/memories` | Lister / ajouter / tout effacer |
| PATCH / DELETE | `/api/memories/{id}` | Modifier / oublier un souvenir |

## Feuille de route

1. ✅ Backend + Docker Compose + streaming
2. ✅ Markdown, longueur adaptative, conversations multiples, mémoire automatique
3. ✅ Atom qui écrit : ntfy, rappels, bot Telegram bidirectionnel — prochain : brief du matin, relances
4. Documents : import de notes et de PDF, puis recherche dedans
5. Outils : Proxmox, recherche web, domotique
6. Accès distant via Tailscale ; plus tard, API externes en secours
