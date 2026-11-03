# Atom

Console web autonome pour un assistant IA auto-hébergé : un seul fichier `index.html`, aucune dépendance, aucun build.
Atom s'incarne dans une sphère de ~3 200 fragments qui se désassemble quand elle réfléchit et se reconstitue avec l'émotion de sa réponse.

## Démarrage

1. Installer Ollama : <https://ollama.com>
2. Télécharger le modèle :

   ```bash
   ollama pull qwen3:4b
   ```

3. Lancer Ollama en autorisant le navigateur à l'appeler (nécessaire si la pastille reste rouge) :

   ```bash
   OLLAMA_ORIGINS=* ollama serve
   ```

4. Ouvrir `index.html` dans le navigateur. La pastille passe au vert quand Ollama répond.

> Sur macOS/Windows avec l'app Ollama déjà lancée, quittez-la avant l'étape 3, ou définissez `OLLAMA_ORIGINS` comme variable d'environnement système puis relancez-la.

## Utilisation

- **Entrée** pour envoyer, **Maj+Entrée** pour un saut de ligne.
- La **puce en bas à droite** affiche l'état de l'entité et ouvre les réglages : URL du serveur, personnalité, souvenirs durables, effacement de l'historique, test des émotions.
- Le **sélecteur de modèle** (en-tête) liste les modèles installés via `/api/tags`.

## Fonctionnement

- Le modèle répond en JSON contraint (schéma passé dans `format`) : `{"reponse": "...", "emotion": "..."}`.
- Émotions : `idle`, `thinking`, `talking`, `joy`, `angry`, `sad`, `surprise`, `fear`, `sleep`.
- Dès l'envoi, l'entité passe en `thinking` (dilatée, relâchée) puis adopte l'émotion renvoyée ; elle revient en veille après quelques secondes, et s'endort après 3 minutes d'inactivité.
- **Mémoire** (localStorage) : l'historique est conservé et les 20 derniers tours sont envoyés au modèle ; les souvenirs durables sont injectés dans le prompt système.

## Feuille de route

1. Streaming token par token, avec pulsation de la sphère à chaque token
2. Mémoire sémantique (RAG `sqlite-vec` + `nomic-embed-text`)
3. Backend FastAPI avec routeur hybride (local → API Mistral)
4. TTS/STT (Whisper + Piper), rendu WebGL au-delà de ~10 000 fragments
