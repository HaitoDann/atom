#!/bin/sh
# Démarre en root uniquement pour remettre les droits des volumes (installations existantes),
# puis lance Atom sous l'utilisateur non privilégié « atom ».
set -e
if [ "$(id -u)" = "0" ]; then
  for d in /data /backups; do
    [ -d "$d" ] && chown -R atom:atom "$d" 2>/dev/null || true
  done
  exec setpriv --reuid=atom --regid=atom --init-groups "$@"
fi
exec "$@"
