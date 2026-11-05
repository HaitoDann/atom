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

### Nouveautés de l'interface

- **Fichiers joints** : trombone, glisser-déposer ou coller. Texte, code, Markdown, CSV, JSON et PDF (texte extrait sur le serveur). Les 12 000 premiers caractères d'un fichier sont lus. Les images ne sont pas encore prises en charge (le modèle actuel ne voit pas).
- **Souvenirs utilisés** : sous une réponse, « 2 souvenirs utilisés » se déplie pour voir ce qu'Atom a pris en compte, oublier un souvenir faux d'un clic, ou ouvrir la conversation passée rappelée.
- **Avis** 👍 / 👎 sur chaque réponse, avec une raison facultative (stockés pour affiner Atom plus tard).
- **Code coloré** en niveaux de gris, **formules** `$…$` et `$$…$$` (KaTeX, chargé à la demande), **liens** détectés automatiquement.
- **Brouillons** conservés par conversation.
- **Modèle par conversation** : chaque conversation garde le modèle avec lequel elle a été menée.
- **Apparence** : densité (confortable / compacte) et largeur (normale / étroite / large) dans Réglages → Apparence.

### L'entité, un familier

- Elle **te regarde** : son regard suit le curseur ; quand tu écris, elle se tourne vers la saisie et frémit à chaque touche.
- Elle **ressent le serveur** : plus le processeur travaille, plus elle respire et tourne vite.
- Elle a un **rythme de vie** : la nuit (23 h – 6 h) elle s'assombrit, ralentit et s'endort plus vite.
- Elle a une **humeur durable** : ses émotions des dernières heures colorent légèrement son état de repos ; la courbe des 24 h est dans le panneau (joyeuse, sereine, neutre, pensive, morose).
- Elle a des **petits gestes** : clignements, coups d'œil, et un « souffle » d'absorption quand elle retient un souvenir.
- **Mode présence** : touche la sphère (ou l'icône dans la barre du haut). Elle quitte son panneau et s'agrandit en plein écran, avec l'heure, la date et son dernier message ; l'écran reste allumé. Touche-la à nouveau (ou `Échap`) : elle se rétracte et reprend sa place pendant que le chat réapparaît. Idéal pour une tablette posée dans la pièce.

### Installer Atom comme une application

Les navigateurs n'autorisent l'installation qu'en **HTTPS** : il faut donc passer par Tailscale (ci-dessous), qui fournit une adresse `https://…ts.net` avec un vrai certificat. Ensuite :
- **Android / Chrome / Edge** : Réglages d'Atom → Apparence → « Installer l'application », ou menu du navigateur → « Installer ».
- **iPhone / iPad (Safari)** : bouton Partager → « Sur l'écran d'accueil ».

## Vitesse

Atom affiche la vitesse réelle mesurée par Ollama (panneau → Système → Vitesse). Réglages → Général → **Mesurer la vitesse** fait un test rapide. Sur CPU, un modèle 4B devrait écrire entre **6 et 12 tokens/s** ; sous 3 tok/s, quelque chose freine.

Réglages déjà appliqués dans `docker-compose.yml` :
- `OLLAMA_NUM_PARALLEL=1` : Ollama ne réserve plus 4 contextes d'avance (la mémoire nécessaire est divisée par 4) ;
- `OLLAMA_KV_CACHE_TYPE=q8_0` + `OLLAMA_FLASH_ATTENTION=1` : contexte compressé, deux fois moins de RAM ;
- `OLLAMA_KEEP_ALIVE=24h` : le modèle reste chargé, pas de rechargement entre deux messages ;
- la mémoire automatique ne relance le modèle que si tu parles de toi (plus pour « 2+2 » ou « merci »).

Si c'est encore lent, vérifie :

1. **La vitesse brute d'Ollama**, sans Atom :

   ```bash
   docker compose exec ollama ollama run qwen3:4b-instruct-2507-q4_K_M --verbose "Bonjour"
   ```

   Regarde la ligne `eval rate` (tokens/s).

2. **Les ressources du conteneur LXC** dans Proxmox (Ressources) : au moins **4 cœurs** et **8 Go de RAM**, et le **swap** pas sollicité :

   ```bash
   free -h
   ```

   Si `Swap used` grimpe pendant une réponse, la RAM manque : augmente-la, ou réduis `ATOM_NUM_CTX=4096` dans `.env`.

3. **Le nombre de threads** : mets `ATOM_NUM_THREADS` au nombre de cœurs donnés au LXC (par ex. `4`), puis `docker compose up -d atom`.

## Sauvegarde

- **Chaque nuit à 3 h 30**, Atom copie toute sa mémoire (conversations, souvenirs, rappels, lien) dans le dossier `backups/` à côté du `docker-compose.yml`, et garde les **7 dernières**. Si le serveur était éteint, une copie est faite au démarrage.
- Réglages → **Sauvegarde** : sauvegarder maintenant, télécharger une copie sur ton PC, restaurer une sauvegarde du serveur ou un fichier `.db`.
- Avant toute restauration, l'état actuel est sauvegardé automatiquement.
- Réglables dans `.env` : `ATOM_BACKUP_TIME`, `ATOM_BACKUP_KEEP`.
- Le dossier `backups/` est sur le même disque que le serveur : télécharge une copie de temps en temps, ou inclus le conteneur dans les sauvegardes Proxmox.

## Mode hybride (Mistral)

Atom répond **en local par défaut**. Il peut s'appuyer sur un modèle Mistral, plus puissant, quand ça vaut le coup.

**Mise en route**

1. Crée un compte sur [console.mistral.ai](https://console.mistral.ai), choisis l'offre gratuite (*Experiment*), puis **API Keys → Create new key**.
2. Dans `.env` : `ATOM_REMOTE_API_KEY=ta_clé`, puis `docker compose up -d atom`.
3. Réglages → **Hybride** : choisis le moteur par défaut et ce que tu acceptes d'envoyer.

**Les moteurs** (réglage par défaut, et sélecteur sous la saisie pour changer ponctuellement)
- **Local** : tout reste sur ton serveur.
- **Auto** : Mistral pour les demandes longues ou complexes (analyse, comparaison, rédaction, architecture…), local pour le reste.
- **Mistral** : toujours Mistral.
- Sous une réponse locale, l'icône ✦ **Réponse approfondie** la régénère avec Mistral.
- Si Mistral ne répond pas (clé refusée, limite atteinte, coupure), Atom repasse en local automatiquement. Les réponses venues de Mistral portent la mention « via Mistral ».

**Confidentialité**
- Quand Mistral répond, il reçoit ton message et le fil de la conversation.
- Tes **souvenirs**, ta **bibliothèque et tes fichiers joints**, et les **résultats de recherche web** ne partent que si tu l'autorises (Réglages → Hybride). Par défaut : seuls les résultats web, déjà publics, sont autorisés.
- Si une demande a besoin de ta bibliothèque ou d'un fichier et que l'envoi n'est pas autorisé, Atom répond en local.
- La mémorisation, la recherche dans tes documents, l'indexation et les embeddings restent **toujours** en local.
- Sur l'offre gratuite de Mistral, tes échanges peuvent servir à améliorer leurs modèles : vérifie les conditions et les réglages de confidentialité de ton compte.

**Limites** : `ATOM_REMOTE_DAILY_LIMIT` (200 par défaut) plafonne les requêtes par jour ; au-delà, Atom reste en local. Modèle : `ATOM_REMOTE_MODEL` ou Réglages → Hybride. Tout fournisseur compatible OpenAI fonctionne en changeant `ATOM_REMOTE_URL` et `ATOM_REMOTE_NAME`.

## Bibliothèque : tes documents et ton code

Barre latérale → **Bibliothèque**.

**Documents** — dépose tes fichiers (PDF, Word `.docx`/`.odt`, texte, Markdown, HTML, CSV, JSON…) dans une collection (« Mes documents », « Administratif »…). Atom les découpe en passages et les indexe. Les PDF scannés (images) ne sont pas encore lus.

**Projets de code** (lecture seule) — « Ajouter un projet de code » :
- **GitHub** : colle l'adresse du dépôt. Pour un dépôt privé, crée un jeton *fine-grained* en lecture seule (github.com → Settings → Developer settings → Personal access tokens → *Contents : Read-only*) et mets-le dans `.env` : `ATOM_GITHUB_TOKEN=github_pat_…`. « Mettre à jour » récupère les derniers changements et ne réindexe que les fichiers modifiés.
- **Dossier du serveur** : place (ou clone) tes projets dans `~/atom/projects/` — ils sont montés en lecture seule. Pour pointer ailleurs (un autre disque, un partage NAS monté sur le LXC) : `ATOM_PROJECTS_HOST_DIR=/chemin` dans `.env`.
- Les dossiers lourds (`node_modules`, `.git`, `dist`, `build`, `venv`…) et les fichiers minifiés sont ignorés.

**Dans la conversation** — le bouton sous la saisie choisit ce qu'Atom consulte :
- **Documents** (par défaut) : Atom puise dans tes collections de documents quand c'est pertinent ;
- **une collection ou un projet précis** : il ne regarde que là (pratique pour « Explique l'architecture de ce projet », « Où est géré le login ? ») ;
- **Sans bibliothèque**.

Les passages utilisés s'affichent sous la réponse (`D1 bail.pdf, p. 4`) ; un clic ouvre l'aperçu du document avec le passage mis en évidence. « Poser une question » depuis la bibliothèque ouvre une conversation déjà ciblée.

## Recherche sur Internet

Un moteur **SearXNG** auto-hébergé tourne avec Atom (service `searxng`, sans port exposé) : il interroge plusieurs moteurs sans traçage. Atom lit ensuite les meilleures pages et répond en citant ses sources, affichées sous la réponse.

- **Atom décide** : s'il ne connaît pas la réponse (actualité, prix, météo, horaires…), il lance lui-même une recherche. Réglages → Général → « Atom cherche de lui-même » pour couper ce comportement.
- **Tu forces** : le bouton globe sous la saisie déclenche une recherche pour ce message.
- Pendant la recherche, des fragments bleus convergent vers la sphère : elle se nourrit.
- Pour désactiver complètement : `ATOM_SEARXNG_URL=` (vide) dans `.env`.

## Le lien avec Atom

Un côté « familier » sans contrainte : **rien ne diminue jamais**, pas de faim ni de punition.

- **Le lien grandit** avec les conversations, les souvenirs, les caresses et la « nourriture » (fichiers joints, recherches). Six stades : Éveil, Curieux, Familier, Complice, Attaché, Inséparable. À chaque stade la sphère gagne des fragments, puis un second anneau (stade 4) et un cœur lumineux (stade 5).
- **Caresser** : passe doucement le curseur sur la sphère ; ses fragments se resserrent, se réchauffent et viennent vers toi au lieu de fuir. **Maintiens le clic** : elle se blottit.
- **Souvenir retenu** : un fragment lumineux part du message et entre dans la sphère.
- Émotions sans traits humains : la colère rend les fragments rouges et frénétiques, la curiosité les fait tourner en spirale, la concentration accélère leur rotation, le bien-être (après une caresse) les rend chauds et denses avec une vibration fine.

## Accéder à Atom hors de chez toi (Tailscale)

[Tailscale](https://tailscale.com) relie tes appareils dans un réseau privé chiffré : rien n'est exposé sur Internet, aucun port à ouvrir sur la box, et il fournit le HTTPS nécessaire à l'appli installable. C'est gratuit pour un usage personnel.

Tailscale tourne comme un conteneur de plus, en **mode espace utilisateur** : il fonctionne dans un LXC sans réglage côté Proxmox et sans VM.

**1. Activer HTTPS** — dans la [console d'administration Tailscale](https://login.tailscale.com/admin/dns) → DNS : active **MagicDNS** et **HTTPS Certificates**.

**2. Activer le service** — dans `.env` :

```
COMPOSE_PROFILES=tailscale
TS_HOSTNAME=atom
```

Facultatif : une clé d'authentification (console → Settings → Keys → *Generate auth key*) dans `TS_AUTHKEY=`. Sans clé, tu te connectes via un lien affiché dans les logs.

**3. Lancer** :

```bash
docker compose up -d
```

```bash
docker compose logs -f tailscale
```

Sans clé, ouvre le lien « To authenticate, visit… » affiché dans les logs et valide. Atom apparaît dans la console Tailscale sous le nom `atom`.

**4. Vérifier** : depuis un appareil connecté à Tailscale, ouvre `https://atom.<ton-tailnet>.ts.net` (le nom exact est dans la console Tailscale, onglet Machines). Le premier chargement prend quelques secondes, le temps d'obtenir le certificat. ntfy est sur `https://atom.<ton-tailnet>.ts.net:8443`.

> Les adresses servies sont réglées dans `tailscale/serve.json`.

**5. Sur le téléphone** : installe l'appli Tailscale, connecte-toi avec le même compte, ouvre l'adresse ci-dessus, puis installe Atom.

**6. Mets à jour `.env`** pour que les notifications pointent vers ces adresses, puis `docker compose up -d` :

```
ATOM_PUBLIC_URL=https://atom.<ton-tailnet>.ts.net
NTFY_BASE_URL=https://atom.<ton-tailnet>.ts.net:8443
```

Dans l'appli ntfy, remplace aussi le serveur par `https://atom.<ton-tailnet>.ts.net:8443`.

> Telegram, lui, fonctionne partout même sans Tailscale.

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
