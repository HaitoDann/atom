#!/usr/bin/env bash
# Met Atom à jour : récupère le code, reconstruit, redémarre, puis vérifie que tout répond.
# Usage : ./update.sh            (depuis le dossier atom)
set -euo pipefail
cd "$(dirname "$0")"

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }

say "1/4 · Récupération du code"
before=$(git rev-parse --short HEAD)
git pull --ff-only
after=$(git rev-parse --short HEAD)
if [ "$before" = "$after" ]; then echo "Déjà à jour ($after)."; else
  echo "Mise à jour $before → $after :"; git log --oneline "$before..$after" | sed 's/^/  · /'; fi

say "2/4 · Sauvegarde de sécurité"
if docker compose ps --status running atom >/dev/null 2>&1 && docker compose exec -T atom true 2>/dev/null; then
  docker compose exec -T atom python -c "from app import db, backup; db.init(); print('  →', backup.create('manual')['name'])" \
    || echo "  (sauvegarde impossible, on continue)"
else
  echo "  Atom n'est pas démarré : pas de sauvegarde."
fi

say "3/4 · Reconstruction et redémarrage"
export ATOM_VERSION="$after"
docker compose pull --quiet --ignore-buildable 2>/dev/null || docker compose pull --quiet || true
docker compose up -d --build --remove-orphans
docker image prune -f >/dev/null 2>&1 || true

say "4/4 · Vérification"
for i in $(seq 1 30); do
  if docker compose exec -T atom python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/auth/status', timeout=2)" 2>/dev/null; then
    echo "  Atom répond (version $after)."
    docker compose ps --format 'table {{.Service}}\t{{.Status}}'
    echo; echo "  Détail des services : Réglages → État dans l'interface."
    exit 0
  fi
  sleep 2
done
echo "  Atom ne répond pas après 60 s. Regarde les logs : docker compose logs --tail=50 atom"
exit 1
