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

### Ergonomie

- **Palette de commandes** (`Ctrl+K`, ou le raccourci affiché dans la recherche) : conversations (titres et contenu), actions, vues, moteur, modèle, thème, réglages, collections, et fichiers du projet en mode Code. Navigation au clavier.
- **Accueil** : dans une conversation vide, l'entité quitte son panneau et accueille au centre ; elle y retourne à ton premier message (désactivable dans Réglages → Apparence).
- **Thème clair**, sombre ou automatique (Réglages → Apparence) ; l'entité et le logo s'adaptent.
- **Sur téléphone** : barre d'onglets en bas (Discussions, Bibliothèque, Code, Atom, Réglages) et gestes — glisser depuis le bord gauche pour les conversations, depuis le bord droit pour l'entité.
- **Glisser-déposer** partout : dans une conversation, le fichier est joint au message ; dans la bibliothèque, il est ajouté à la collection ; déposé **sur l'entité**, il est rangé dans ta bibliothèque.
- **Signaux** : quand Atom cite une source ou utilise un souvenir, un signal lumineux part de l'entité vers l'élément cité.

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

## Sécurité

- **Mot de passe** : au premier lancement, l'interface demande d'en créer un (8 caractères minimum). Tout l'accès aux données (`/api/…`) est refusé sans session. Pour le fixer d'avance : `ATOM_PASSWORD=…` dans `.env`.
- **Appareils** : chaque navigateur reste connecté 90 jours après sa dernière visite. Réglages → **Sécurité** : liste des appareils, déconnexion à distance, changement de mot de passe (les autres appareils sont alors déconnectés).
- **Essais limités** : après 5 mauvais mots de passe en 10 minutes, l'adresse est bloquée 1 min, puis 5, puis 30.
- **Requêtes protégées** : toute modification doit venir de l'interface (en-tête dédié), ce qui bloque les attaques depuis un autre site.
- **Mot de passe oublié** :

  ```bash
  docker compose exec atom python -m app.auth reset
  ```

  puis ouvre Atom pour en créer un nouveau.
- **Accès Tailscale uniquement** : `ATOM_BIND=127.0.0.1` dans `.env`, puis `docker compose up -d atom`. Le port 8000 n'est plus ouvert au réseau local ; Atom reste joignable via `https://atom.<ton-tailnet>.ts.net`.
- Telegram n'est pas concerné : seuls les identifiants de `ATOM_TELEGRAM_ALLOWED` sont servis.

## Mise à jour

```bash
./update.sh
```

Le script récupère le code, fait une **sauvegarde de sécurité**, reconstruit et redémarre les services, puis vérifie qu'Atom répond. Réglages → **État** vérifie ensuite chaque service (modèles, recherche, notifications, Telegram, mode hybride, disque, sauvegardes, bibliothèque) et indique quoi faire en cas de problème.

## Tests

```bash
pip install -r api/requirements.txt -r api/requirements-dev.txt
```

```bash
cd api && python -m pytest -q
```

Les tests tournent sans modèle ni Internet (mode test) ; ils sont aussi lancés automatiquement par GitHub Actions à chaque envoi de code.

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

- **Chaque nuit à 3 h 30**, Atom copie toute sa mémoire (conversations, souvenirs, rappels) dans le dossier `backups/` à côté du `docker-compose.yml`, et garde les **7 dernières**. Si le serveur était éteint, une copie est faite au démarrage.
- Réglages → **Sauvegarde** : sauvegarder maintenant, télécharger une copie sur ton PC, restaurer une sauvegarde du serveur ou un fichier `.db`.
- Avant toute restauration, l'état actuel est sauvegardé automatiquement.
- Réglables dans `.env` : `ATOM_BACKUP_TIME`, `ATOM_BACKUP_KEEP`.
- Le dossier `backups/` est sur le même disque que le serveur : télécharge une copie de temps en temps, ou inclus le conteneur dans les sauvegardes Proxmox.

## Mode hybride (API distantes)

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

**Limites** : `ATOM_REMOTE_DAILY_LIMIT` (200 par défaut) plafonne les requêtes par jour ; au-delà, Atom passe au fournisseur suivant, puis au local. Tout fournisseur compatible OpenAI fonctionne en changeant `ATOM_REMOTE_URL` et `ATOM_REMOTE_NAME`.

**Plusieurs fournisseurs gratuits**

Ajoute-en autant que tu veux dans `.env`, puis `docker compose up -d atom` :

```
ATOM_CEREBRAS_API_KEY=...
ATOM_GEMINI_API_KEY=...
```

Pour un fournisseur connu, la clé suffit ; `ATOM_PROVIDERS=…` sert pour un fournisseur non listé ou pour imposer l'ordre.

- Fournisseurs connus (adresse, modèle par défaut et famille déjà renseignés) : `groq`, `cerebras`, `gemini`, `openrouter`, `github`, `mistral`. Pour un autre : `ATOM_<ID>_URL` et `ATOM_<ID>_MODEL`.
- Chacun a son **quota du jour** (`ATOM_<ID>_LIMIT`), sa **famille** de modèles et une **force** estimée (`ATOM_<ID>_STRENGTH`, de 1 à 3).
- Réglages → Connexions → **Fournisseurs** : choisis le **principal** et le modèle de chacun, et suis l'utilisation du jour.
- **Relais automatique** : si le principal est indisponible (limite atteinte, panne, quota du jour), Atom passe au suivant, du plus fort au plus faible, puis au local. Un fournisseur qui renvoie « limite atteinte » est mis en pause 2 minutes.
- **Données privées** : un fournisseur avec `ATOM_<ID>_PRIVATE=0` ne reçoit **jamais** tes souvenirs, documents ni fichiers, même si tu les as autorisés. C'est le réglage par défaut pour `gemini` et `openrouter`, dont les offres gratuites peuvent réutiliser les données.
- Les modèles par défaut changent souvent chez les fournisseurs : si l'un d'eux affiche « modèle introuvable » dans l'écran État, choisis-en un autre dans la liste.

## Modèles locaux : essayer et comparer

Réglages → Système → **Modèles locaux** :

- **Modèles installés** : **Utiliser** pour en changer, ou **Supprimer** pour libérer de l'espace disque. Le modèle actif ne peut pas être supprimé.
- **Essayer un autre modèle** : des suggestions avec leur taille, et l'installation de n'importe quel modèle Ollama par son nom. Le téléchargement se fait en arrière-plan avec une barre de progression, et un avertissement s'affiche si le modèle dépasse la mémoire disponible.
  - `qwen3:30b-a3b-instruct-2507-q4_K_M` : modèle « à experts » de 30 milliards de paramètres, dont environ 3 sont actifs par mot. Il est nettement plus capable qu'un 4B, pour une vitesse proche sur processeur, mais demande environ 19 Go de RAM.
  - `qwen2.5-coder:7b` : spécialisé dans le code.
- **Comparatif** : les mêmes questions (raisonnement, rédaction, code, connaissances, ou ta propre question) sont posées à 1 à 4 modèles, l'un après l'autre. Les **API distantes** peuvent être ajoutées : elles ne reçoivent que les questions du comparatif, et chaque question compte dans leur quota du jour. Un bouton « En faire le principal » permet de choisir un fournisseur depuis le comparatif. Les réponses s'affichent côte à côte avec la vitesse d'écriture, le délai avant le premier mot et le temps de chargement. **Utiliser ce modèle** l'adopte directement. À la fin, les modèles non retenus sont déchargés de la mémoire.

## Mode Code

Barre latérale → **Code** : parcourir un projet de la bibliothèque (GitHub ou dossier du serveur), et faire proposer des modifications.

**Disposition** (inspirée de VS Code et Zed)
- **Barre d'activité** à gauche : **Fichiers**, **Recherche** dans le code (Ctrl+Maj+F), **Git** (Ctrl+Maj+G) et **Tests**. Un seul panneau s'affiche à la fois, et un point signale des modifications ou des tests en échec.
- **Onglet Agent** épinglé, qui sert d'accueil du projet : la saisie de la tâche, des idées en un clic (expliquer le projet, trouver des bugs, ajouter des tests, documenter, revue de sécurité…) et les tâches récentes.
- **Ouverture rapide** : **Ctrl+P**, puis quelques lettres du nom. Les fichiers récents apparaissent en premier.
- **Barre d'état** : branche, nombre de modifications, commits à pousser et état des tests à gauche ; fichier actif, nombre de lignes et sélection à droite. Un clic ouvre le panneau correspondant.
- Le panneau de l'entité est replié par défaut dans cette vue, et le bouton en haut à droite le rouvre.
- L'agent lit automatiquement les **consignes du projet** s'il y en a à la racine : `AGENTS.md`, `CLAUDE.md`, `.cursorrules` ou `.github/copilot-instructions.md`.

- **Arborescence** repliable, **filtre** par nom de fichier, et **recherche dans le contenu** (loupe) avec les lignes trouvées — un clic ouvre le fichier à la bonne ligne.
- **Onglets** (8 fichiers ouverts au plus), **numéros de ligne**, **coloration syntaxique** par langage (Python, JS/TS, Go, Rust, C/C++, Java, PHP, Shell, SQL, YAML, TOML, JSON, HTML, CSS…), **aperçu** des fichiers Markdown.
- **Demander à Atom** : clique sur un numéro de ligne (Maj+clic pour une plage), puis **Expliquer**, **Relire** (bugs, cas oubliés) ou **Demander…** — le passage est joint à une nouvelle conversation ciblée sur le projet. « Expliquer le fichier » fait de même pour tout le fichier.
- **Modifier…** (sur le fichier, ou sur une sélection de lignes) : écris la consigne (« gère le cas où la liste est vide »), Atom propose une version réécrite et le serveur affiche le **diff** (lignes ajoutées / retirées). Rien n'est écrit tant que tu n'as pas cliqué **Appliquer**. Fichier entier jusqu'à 400 lignes ; au-delà, sélectionne la partie à changer. Avec le mode hybride et « fichiers et bibliothèque » autorisés, tu peux cocher l'API distante pour cette proposition.
- **Appliquer** n'est possible que sur les **dépôts GitHub clonés par Atom** (`data/repos`). Les dossiers du serveur (`/projects`) sont montés en **lecture seule** : télécharge le **patch** et applique-le chez toi (`git apply fichier.patch`).
- **Agent** (icône ✦ à côté du sélecteur de projet) : tu confies une tâche sur **tout le projet**, par exemple « ajoute une validation de l'e-mail dans le formulaire d'inscription ».
  - L'agent écrit d'abord un **plan**, puis enchaîne seul : lister, lire, chercher, modifier, créer des fichiers. Chaque étape s'affiche en direct, et un clic sur une étape montre son résultat.
  - Il travaille sur une **copie en mémoire** : rien n'est écrit sur le disque. À la fin, tu vois un **diff par fichier** et tu coches ce que tu gardes, puis **Appliquer la sélection** (dépôts clonés), **Patch** ou **Abandonner**. Le commit se fait ensuite dans le panneau Git.
  - L'agent **tourne sur le serveur** : tu peux recharger la page, la fermer ou passer sur ton téléphone. En revenant, la tâche en cours ou terminée s'affiche telle quelle.
  - **Historique** des tâches par projet (menu en haut de l'agent), et **Poursuivre…** pour enchaîner une demande sur le résultat précédent. L'agent garde alors son contexte et les modifications pas encore appliquées.
  - Le mode Code retient la vue, le projet, les fichiers ouverts et le fichier actif d'un chargement à l'autre.
  - Garde-fous : il doit lire un passage avant de le modifier, il n'exécute **aucune commande**, il ne sort pas du projet et ne touche pas à `.git`. Il est limité à 25 étapes, et le bouton **Arrêter** est toujours disponible. Si un fichier a changé entre-temps, il est signalé en conflit au lieu d'être écrasé.
  - Budget : les offres gratuites limitent la taille des requêtes (Groq : environ 8 000 tokens par minute). L'agent raccourcit les anciens résultats et lit les fichiers par morceaux pour rester sous la limite. Quand le fournisseur demande de patienter quelques secondes, il attend. Réglable avec `ATOM_<ID>_BUDGET`.
  - Moteur : l'**API distante** est recommandée (Groq, Gemini…), car un petit modèle local suit mal une suite d'actions. Le code ne part que si tu as autorisé « Ma bibliothèque et mes fichiers », et seulement vers les fournisseurs qui acceptent les données privées. Sinon, l'agent tourne en local.
- **Git** (dépôts GitHub clonés par Atom), en haut de l'arborescence — chaque action est un bouton que tu cliques, jamais une décision du modèle :
  - **branche** active et changement de branche (les fichiers sont réindexés), **＋ branche** (les modifications et commits non poussés la suivent) ;
  - fichiers modifiés à **cocher**, **Commit…** avec **Proposer** (Atom écrit le message à partir du diff, en local), **Annuler** par fichier ou **Tout annuler** ;
  - **Pousser** (avec confirmation) puis lien **Ouvrir une pull request**. Atom **ne pousse jamais sur la branche principale** du dépôt (il propose de créer une branche `atom/…` au moment du commit) et ne fait **jamais de force-push** ;
  - **Patch** pour télécharger les modifications en cours.
  - Il faut un jeton GitHub **fine-grained** limité à tes dépôts avec **Contents: Read and write** dans `ATOM_GITHUB_TOKEN` (`.env`), et `ATOM_GIT_NAME` / `ATOM_GIT_EMAIL` pour signer les commits. Le jeton n'est jamais écrit dans les dépôts clonés.
- **Mettre à jour** récupère les derniers changements du dépôt (si un fichier modifié localement change aussi sur GitHub, annule d'abord ta modification).

## Espaces, canevas, recherche approfondie, analyse de données, schémas

**Espaces** (comme les Projets de ChatGPT et Claude). Barre latérale → **Espaces** → ＋ : un nom, des **consignes** (« je développe un shell en Go, réponds en technique ») et, si tu veux, des **collections** de la bibliothèque.
- Dans un espace, la liste ne montre que ses conversations, et les nouvelles conversations y sont rangées.
- Atom suit les consignes de l'espace et cherche d'abord dans ses collections.
- Ctrl+K permet de ranger la conversation ouverte dans un espace, ou de l'en retirer. Supprimer un espace garde ses conversations.

**Canevas** (comme Canvas et Artifacts). Sous une réponse, l'icône **document** ouvre son contenu dans un panneau d'édition à droite. Tu peux aussi faire Ctrl+K → « Nouveau canevas ».
- Tu écris directement : l'enregistrement est automatique.
- Tu peux demander à Atom de modifier **tout le document** ou **seulement la partie sélectionnée**, avec une consigne libre ou en un clic : corriger, raccourcir, développer, plus formel, plus simple, en anglais, structurer.
- Chaque modification crée une **version** : le menu en haut permet de revenir en arrière. Il y a aussi un aperçu Markdown, la copie et le téléchargement.

**Recherche approfondie** (comme Deep Research). Bouton **bibliothèque** à côté du globe, puis ta question.
- Atom établit un plan de 3 à 6 recherches, lit les pages, prend des notes sourcées, fait une passe de vérification (ce qui manque ou se contredit), puis rédige un **rapport** : en bref, des sections, des sources citées [n] et les points d'attention.
- Compte 1 à 3 minutes, avec les étapes affichées en direct.
- Seules la question et des pages publiques partent vers l'API distante.

**Analyse de données** (comme Code Interpreter), qui demande le bac à sable. Joins un **CSV, Excel, JSON ou Parquet**, puis pose ta question (« total des ventes par mois, avec un graphique »).
- Atom lit le fichier, écrit un script Python (pandas, matplotlib), l'exécute **sans réseau** dans le bac à sable, le corrige s'il échoue (2 essais), puis explique les résultats.
- Les **graphiques** s'affichent dans la réponse, et le script reste consultable.
- Le fichier ne quitte pas le serveur : seuls un aperçu et les résultats chiffrés partent vers le modèle, et vers une API distante seulement si tu as autorisé l'envoi des fichiers.
- Les bibliothèques Python (environ 100 Mo) sont téléchargées une seule fois.

**Schémas**. Atom dessine les architectures, processus, cartes mentales et chronologies avec **Mermaid**, rendus aux couleurs du thème. Sous chaque schéma : copier le code ou télécharger le SVG.

**Règles de projet** (mode Code, comme les règles de Cursor). Dans l'onglet Agent, **Règles du projet** liste ce que l'agent doit toujours respecter (« utiliser des tabulations », « tests avec testify »). Quand tu corriges l'agent (« jamais… », « utilise plutôt… »), il te propose de **retenir** la consigne. Les fichiers `AGENTS.md` et `CLAUDE.md` du dépôt sont aussi lus.

## Bac à sable : exécuter les tests (mode Code)

Atom peut lancer les tests d'un projet dans un **conteneur Docker jetable**, et l'agent peut vérifier lui-même que son code compile et passe les tests.

**Activation** (désactivé par défaut), dans `.env` :
```
COMPOSE_FILE=docker-compose.yml:docker-compose.sandbox.yml
```
puis `./update.sh`. L'écran État affiche « Bac à sable : actif ».

**Utilisation**
- Code → bloc **Tests** sous le panneau Git : **▶ Lancer les tests**. La commande est détectée selon le projet : `go test ./...`, `cargo test`, `npm test` ou `pytest`. **modifier** permet de la changer pour ce projet, par exemple `go test ./shell/...`.
- L'agent dispose d'un outil **test** : après ses modifications, il lance les tests *avec ses changements non appliqués*, lit les erreurs, corrige et relance (3 essais au plus).
- Dans les résultats de l'agent, **Tester ces modifications** fait la même chose à la demande.

**Isolation**
- Deux conteneurs neufs, supprimés après usage. Le premier récupère les dépendances **avec réseau, sans exécuter de script** (`go mod download`, `cargo fetch`, `npm ci --ignore-scripts`, `pip download`) dans un cache persistant (volume `atom-sandbox-cache`). Le second lance les tests **sans réseau**.
- Les conteneurs n'ont aucun privilège (`cap-drop ALL`, `no-new-privileges`) et sont limités à 2 Go de mémoire, 2 processeurs, 512 processus et 5 minutes. Ces limites se règlent avec `ATOM_SANDBOX_MEMORY_MB`, `ATOM_SANDBOX_CPUS` et `ATOM_SANDBOX_TIMEOUT`.
- Le conteneur de test ne voit ni le socket Docker, ni les données d'Atom, ni ton réseau. Le projet y est copié : tes fichiers ne sont jamais modifiés.
- ⚠ Pour créer ces conteneurs, Atom a besoin du socket Docker, qui donne le contrôle de Docker sur le serveur. Garde un mot de passe solide et n'expose Atom que par Tailscale.

**Espace disque** : les images sont légères et téléchargées une seule fois, au premier test du langage concerné : `golang:1.23-alpine` environ 250 Mo, `node:22-alpine` environ 150 Mo, `python:3.12-slim` environ 130 Mo, `rust:1-slim` environ 700 Mo. Pour libérer la place : `docker image rm …` et `docker volume rm atom-sandbox-cache`.

## Atelier multi-IA (désactivé par défaut)

Pour une demande importante, plusieurs IA collaborent. Réglages → **Atelier** → « Activer l'atelier », puis le bouton **Atelier** (icône de groupe) sous la saisie pour le message suivant.

- **Rédaction puis relecture** : un rédacteur écrit, un relecteur critique, une version corrigée est produite (1 à 3 tours).
- **Comité et arbitre** : deux propositions indépendantes, un arbitre fait la synthèse.
- **Débat contradictoire** : deux positions opposées, un arbitre tranche — utile pour une décision.
- Chaque rôle est en **Automatique** par défaut, ou tenu par le modèle **local** ou par un fournisseur précis. En automatique :
  - le modèle le **plus fort** rédige ;
  - le relecteur vient d'une **autre famille** (Llama, Qwen, Gemini…), qui ne fait pas les mêmes erreurs ;
  - l'**arbitre n'est jamais le plus faible** : c'est le plus fort disponible, et si possible un troisième fournisseur ;
  - les réglages affichent qui tient chaque rôle, avec un avertissement si un choix manuel affaiblit l'atelier.
- **Relecture avec une grille** : exactitude (faits, chiffres, code), consignes oubliées, cohérence, utilité. Chaque problème est classé `[bloquant]`, `[important]` ou `[mineur]`, avec une section « Non vérifiable » pour ce que le relecteur ne peut pas confirmer. La correction traite tout ce qui est bloquant ou important et retire ou signale ce qui n'est pas vérifiable. Si le verdict est « OK », la correction est **sautée** : un appel de moins.
- Un participant indisponible est remplacé par le fournisseur suivant (mention « relais »), puis par le local.
- Le travail intermédiaire de chaque IA est visible dans une carte repliable au-dessus de la réponse finale.
- Confidentialité : l'atelier ne reçoit que ta demande et les derniers échanges (ni souvenirs, ni bibliothèque, ni fichiers). Coût : jusqu'à 3 étapes ou plus par demande.

## Bibliothèque : tes documents et ton code

Barre latérale → **Bibliothèque**.

**Documents** — dépose tes fichiers (PDF, Word `.docx`/`.odt`, texte, Markdown, HTML, CSV, JSON…) dans une collection (« Mes documents », « Administratif »…). Atom les découpe en passages et les indexe. Les **PDF scannés et les images** (photos de documents, captures) sont lus par OCR (Tesseract, français + anglais, sur le serveur) : page par page, seules les pages sans texte passent par l'OCR. Compte quelques secondes par page. Même chose pour une pièce jointe dans une discussion (30 pages max).

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
- Pendant la recherche, des fragments bleus convergent vers la sphère.
- Pour désactiver complètement : `ATOM_SEARXNG_URL=` (vide) dans `.env`.

## L'entité

- **Souvenir retenu** : un fragment lumineux part du message et entre dans la sphère.
- **Apparence : maillage** (par défaut) — la sphère est un réseau de ~360 nœuds régulièrement répartis et reliés à leurs voisins, l'arrière estompé dans la profondeur, une poussière intérieure discrète, et des **signaux lumineux** qui parcourent les liens (rares au repos, nombreux quand Atom réfléchit, parle, cherche ou consulte une autre IA). Toutes les émotions et animations s'appliquent au réseau ; dans l'atelier, les liens entre amas se rompent. Réglages → Entité → « Fragments » pour revenir à la sphère de poussière d'origine.
- Situations : **consulter une IA distante** (ondes de fragments lavande qui partent de la sphère), **atelier** (la sphère se divise en amas qui tournent ensemble, celui qui travaille s'éclaire, puis ils fusionnent pour la réponse finale), **lecture** de code ou de documents (les fragments se rangent en lignes, un balayage lumineux les parcourt), **indexation** (fragments blancs absorbés), **sauvegarde** (contraction et anneau qui se referme), **secours ou erreur** (brève perturbation par bandes). Toutes prévisualisables dans Réglages → Entité.
- Émotions sans traits humains : la colère rend les fragments rouges et frénétiques, la curiosité les fait tourner en spirale, la concentration accélère leur rotation.

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
