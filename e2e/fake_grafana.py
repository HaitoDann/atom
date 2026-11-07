"""Faux Grafana pour les tests de bout en bout : répond sous /grafana/… comme le ferait Grafana (sous-chemin).

Vérifie que l'interface d'Atom affiche bien le tableau de bord à travers son relais (/grafana/), dans un cadre.
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8798


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (nom imposé par http.server)
        if not self.path.startswith("/grafana/"):
            self.send_error(404)
            return
        if self.path.startswith("/grafana/api/health"):
            body, ctype = json.dumps({"database": "ok"}).encode(), "application/json"
        else:
            cookie = self.headers.get("Cookie", "")
            body = (f"<!doctype html><title>Grafana factice</title><h1 id='g'>Grafana factice</h1>"
                    f"<p id='path'>{self.path}</p><p id='cookie'>{cookie or 'aucun cookie'}</p>").encode()
            ctype = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
