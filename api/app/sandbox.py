"""Bac à sable : exécuter les tests d'un projet dans un conteneur Docker jetable.

Activation (désactivé par défaut) : ATOM_SANDBOX=1 et le socket Docker monté dans le conteneur d'Atom
(voir docker-compose.sandbox.yml). Atom parle directement à l'API Docker, sans CLI.

Déroulement :
1. une copie du projet (disque + modifications de l'agent non appliquées) est envoyée dans un conteneur neuf ;
2. dépendances : téléchargées AVEC réseau mais sans exécuter de script (go mod download, cargo fetch,
   npm ci --ignore-scripts, pip download), dans un cache persistant (volume atom-sandbox-cache) ;
3. tests : nouveau conteneur SANS réseau, limité en mémoire / processeur / processus / durée,
   sans privilèges (cap-drop ALL, no-new-privileges) ; puis il est supprimé.
Le conteneur de test ne voit ni le socket Docker, ni les données d'Atom, ni ton réseau.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import secrets
import tarfile
import time
from pathlib import Path
from typing import AsyncIterator

import httpx

from . import db, library

log = logging.getLogger("atom.sandbox")

SOCKET = os.getenv("ATOM_DOCKER_SOCKET", "/var/run/docker.sock")
# Recommandé : passer par un proxy du socket (docker-compose.sandbox.yml) plutôt que monter le socket lui-même.
DOCKER_HOST = os.getenv("ATOM_DOCKER_HOST", "").replace("tcp://", "http://").rstrip("/")
ENABLED = os.getenv("ATOM_SANDBOX", "0").lower() in ("1", "true", "oui", "yes", "on")
TIMEOUT = int(os.getenv("ATOM_SANDBOX_TIMEOUT", "300"))
MEMORY = int(os.getenv("ATOM_SANDBOX_MEMORY_MB", "2048"))
CPUS = float(os.getenv("ATOM_SANDBOX_CPUS", "2"))
CACHE_VOLUME = "atom-sandbox-cache"
MAX_UPLOAD = 200 * 1024 * 1024
SKIP = {".git", "node_modules", "target", "dist", "build", "__pycache__", ".venv", "venv", ".next", ".cache"}

# Images « légères » par défaut (l'espace disque compte) ; remplaçables par ATOM_SANDBOX_IMAGE_<LANGAGE>.
TOOLCHAINS = {
    "go": {
        "marker": "go.mod", "image": "golang:1.23-alpine",
        "env": ["GOMODCACHE=/cache/go/mod", "GOCACHE=/cache/go/build", "GOFLAGS=-mod=mod", "GOTOOLCHAIN=local",
                "CGO_ENABLED=0", "GOPROXY=https://proxy.golang.org,direct"],
        "fetch": "go mod download", "test": "go test ./...",
    },
    "rust": {
        "marker": "Cargo.toml", "image": "rust:1-slim",
        "env": ["CARGO_HOME=/cache/cargo", "CARGO_TARGET_DIR=/cache/target/{proj}"],
        "fetch": "cargo fetch", "test": "cargo test --offline",
    },
    "node": {
        "marker": "package.json", "image": "node:22-alpine",
        "env": ["npm_config_cache=/cache/npm"],
        "fetch": "if [ -f package-lock.json ]; then npm ci --ignore-scripts; else npm install --ignore-scripts; fi",
        "test": "if [ -f package-lock.json ]; then npm ci --offline --ignore-scripts; else npm install --offline --ignore-scripts; fi >/dev/null && npm test",
    },
    "python": {
        "marker": ["pyproject.toml", "requirements.txt", "setup.py"], "image": "python:3.12-slim",
        "env": ["PIP_DISABLE_PIP_VERSION_CHECK=1", "PYTHONDONTWRITEBYTECODE=1"],
        "fetch": "pip download -q -d /cache/pip pytest $( [ -f requirements.txt ] && echo -r requirements.txt )",
        "test": "pip install -q --no-index --find-links /cache/pip pytest $( [ -f requirements.txt ] && echo -r requirements.txt ) "
                "&& python -m pytest -q",
    },
}


def enabled() -> bool:
    return ENABLED and (bool(DOCKER_HOST) or Path(SOCKET).exists())


def status() -> dict:
    if not ENABLED:
        return {"enabled": False, "reason": "désactivé (ATOM_SANDBOX=1 et docker-compose.sandbox.yml pour l'activer)"}
    if not DOCKER_HOST and not Path(SOCKET).exists():
        return {"enabled": False, "reason": f"socket Docker absent ({SOCKET}) : ajoute docker-compose.sandbox.yml"}
    return {"enabled": True, "reason": "", "via": "proxy" if DOCKER_HOST else "socket"}


# Liste blanche : seules les opérations dont le bac à sable a besoin. Toute autre requête Docker est refusée,
# et une création de conteneur privilégié ou montant un dossier de l'hôte est bloquée.
ALLOWED = [
    ("GET", re.compile(r"^/images/[^/]+(/[^/]+)?/json$")), ("POST", re.compile(r"^/images/create$")),
    ("POST", re.compile(r"^/containers/create$")), ("GET", re.compile(r"^/containers/json$")),
    ("PUT", re.compile(r"^/containers/[0-9a-f]+/archive$")), ("GET", re.compile(r"^/containers/[0-9a-f]+/archive$")),
    ("POST", re.compile(r"^/containers/[0-9a-f]+/(start|wait|kill)$")), ("GET", re.compile(r"^/containers/[0-9a-f]+/logs$")),
    ("DELETE", re.compile(r"^/containers/[0-9a-f]+$")),
]


class DockerRefused(RuntimeError):
    pass


def check_request(method: str, path: str, body: bytes | None) -> None:
    if not any(m == method and rx.match(path) for m, rx in ALLOWED):
        raise DockerRefused(f"requête Docker non autorisée : {method} {path}")
    if path == "/containers/create":
        spec = json.loads(body or b"{}")
        hc = spec.get("HostConfig") or {}
        if hc.get("Privileged") or hc.get("Binds") or hc.get("PidMode") == "host" or hc.get("NetworkMode") == "host" \
                or hc.get("CapAdd") or hc.get("Devices") or any(m.get("Type") != "volume" for m in hc.get("Mounts") or []) \
                or (spec.get("Labels") or {}).get("atom") != "sandbox":
            raise DockerRefused("conteneur refusé : privilèges, accès à l'hôte ou étiquette manquante")


async def _guard(request: httpx.Request) -> None:
    body = request.content if request.method == "POST" and request.url.path == "/containers/create" else None
    check_request(request.method, request.url.path, body)


def _client() -> httpx.AsyncClient:
    hooks = {"request": [_guard]}
    if DOCKER_HOST:
        return httpx.AsyncClient(base_url=DOCKER_HOST, timeout=httpx.Timeout(30, read=600), event_hooks=hooks)
    return httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=SOCKET), base_url="http://docker",
                             timeout=httpx.Timeout(30, read=600), event_hooks=hooks)


# ---------------------------------------------------------------- projet → archive


def detect(files: list[str]) -> str | None:
    top = {f for f in files if "/" not in f}
    for lang, t in TOOLCHAINS.items():
        markers = t["marker"] if isinstance(t["marker"], list) else [t["marker"]]
        if any(m in top for m in markers):
            return lang
    return None


def default_command(cid: int, files: list[str]) -> str:
    saved = db.kv_get(f"sandbox:cmd:{cid}")
    if saved:
        return saved
    lang = detect(files)
    return TOOLCHAINS[lang]["test"] if lang else ""


def set_command(cid: int, cmd: str) -> None:
    db.kv_set(f"sandbox:cmd:{cid}", cmd.strip())


def snapshot(cid: int, overlay: dict[str, str] | None = None) -> tuple[bytes, list[str]]:
    """Archive tar du projet (fichiers du disque + modifications en mémoire) placée dans /work."""
    col = library.get_collection(cid)
    if not col or col["kind"] != "code":
        raise FileNotFoundError("projet")
    root = library._code_root(col).resolve()
    overlay = overlay or {}
    buf = io.BytesIO()
    names: list[str] = []
    total = 0
    with tarfile.open(fileobj=buf, mode="w") as tar:
        d = tarfile.TarInfo("work"); d.type = tarfile.DIRTYPE; d.mode = 0o777
        tar.addfile(d)
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [x for x in dirnames if x not in SKIP]
            for f in filenames:
                p = Path(dirpath) / f
                rel = str(p.relative_to(root))
                if rel in overlay or p.is_symlink():
                    continue
                try:
                    size = p.stat().st_size
                except OSError:
                    continue
                total += size
                if total > MAX_UPLOAD:
                    raise ValueError("projet trop gros pour le bac à sable (200 Mo max hors dépendances)")
                ti = tarfile.TarInfo(f"work/{rel}"); ti.size = size; ti.mode = 0o666
                with p.open("rb") as fh:
                    tar.addfile(ti, fh)
                names.append(rel)
        for rel, content in overlay.items():
            data = content.encode()
            ti = tarfile.TarInfo(f"work/{rel}"); ti.size = len(data); ti.mode = 0o666
            tar.addfile(ti, io.BytesIO(data))
            names.append(rel)
    return buf.getvalue(), names


# ---------------------------------------------------------------- Docker


_collected: dict[str, bytes] = {}


def demux(raw: bytes) -> str:
    """Journaux Docker sans TTY : trames [type, 0, 0, 0, taille(4 octets)] + données."""
    out, i = [], 0
    while i + 8 <= len(raw):
        size = int.from_bytes(raw[i + 4:i + 8], "big")
        out.append(raw[i + 8:i + 8 + size])
        i += 8 + size
    if not out and raw:
        return raw.decode("utf-8", "replace")
    return b"".join(out).decode("utf-8", "replace")


async def _ensure_image(c: httpx.AsyncClient, image: str) -> AsyncIterator[str]:
    r = await c.get(f"/images/{image}/json")
    if r.status_code == 200:
        return
    yield f"Téléchargement de l'image {image} (une seule fois)…"
    name, _, tag = image.partition(":")
    async with c.stream("POST", "/images/create", params={"fromImage": name, "tag": tag or "latest"}) as resp:
        async for line in resp.aiter_lines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get("error"):
                raise RuntimeError(f"image {image} : {ev['error']}")


async def _run_container(c: httpx.AsyncClient, image: str, cmd: str, env: list[str], archive: bytes,
                         network: bool, timeout: int, collect: str | None = None) -> tuple[int, str, float]:
    name = f"atom-sandbox-{secrets.token_hex(4)}"
    body = {
        "Image": image, "Cmd": ["sh", "-c", cmd], "WorkingDir": "/work", "Env": env + ["HOME=/tmp"],
        "Labels": {"atom": "sandbox"}, "AttachStdout": False, "AttachStderr": False, "Tty": False,
        "HostConfig": {
            "NetworkMode": "bridge" if network else "none",
            "Memory": MEMORY * 1024 * 1024, "MemorySwap": MEMORY * 1024 * 1024, "NanoCpus": int(CPUS * 1e9),
            "PidsLimit": 512, "CapDrop": ["ALL"], "SecurityOpt": ["no-new-privileges"],
            "Privileged": False, "IpcMode": "private", "Ulimits": [{"Name": "nofile", "Soft": 4096, "Hard": 4096}],
            "Mounts": [{"Type": "volume", "Source": CACHE_VOLUME, "Target": "/cache"}],
            "Tmpfs": {"/tmp": "rw,size=512m"},
        },
    }
    r = await c.post("/containers/create", params={"name": name}, json=body)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"création du conteneur impossible : {r.text[:200]}")
    cid = r.json()["Id"]
    t0 = time.time()
    try:
        r = await c.put(f"/containers/{cid}/archive", params={"path": "/"}, content=archive,
                        headers={"Content-Type": "application/x-tar"})
        if r.status_code != 200:
            raise RuntimeError(f"copie du projet impossible : {r.text[:200]}")
        await c.post(f"/containers/{cid}/start")
        try:
            w = await asyncio.wait_for(c.post(f"/containers/{cid}/wait"), timeout=timeout)
            code = int(w.json().get("StatusCode", -1))
        except asyncio.TimeoutError:
            await c.post(f"/containers/{cid}/kill")
            code = 124
        logs = await c.get(f"/containers/{cid}/logs", params={"stdout": 1, "stderr": 1, "tail": 400})
        out = demux(logs.content)
        if collect:   # fichiers produits (ex. graphiques) : récupérés avant suppression du conteneur
            arc = await c.get(f"/containers/{cid}/archive", params={"path": collect})
            _collected[cid] = arc.content if arc.status_code == 200 else b""
        if code == 124:
            out += f"\n[Atom] Arrêté au bout de {timeout} s."
        elif code == 137:
            out += f"\n[Atom] Arrêté : mémoire dépassée ({MEMORY} Mo)."
        return code, out, time.time() - t0
    finally:
        await c.delete(f"/containers/{cid}", params={"force": 1})


async def run(cid: int, command: str | None = None, overlay: dict[str, str] | None = None,
              fetch: bool = True) -> AsyncIterator[dict]:
    """Événements : step(message), result(code, output, duration, command)."""
    if not enabled():
        yield dict(type="result", code=-1, output="Bac à sable " + status()["reason"], duration=0, command=command or "")
        return
    archive, files = await asyncio.to_thread(snapshot, cid, overlay)
    lang = detect(files)
    command = (command or default_command(cid, files)).strip()
    if not command:
        yield dict(type="result", code=-1, output="Type de projet non reconnu : indique la commande de test.", duration=0, command="")
        return
    tc = TOOLCHAINS.get(lang or "", {})
    image = os.getenv(f"ATOM_SANDBOX_IMAGE_{(lang or 'custom').upper()}") or tc.get("image") or os.getenv("ATOM_SANDBOX_IMAGE", "alpine:3.20")
    env = [e.format(proj=cid) for e in tc.get("env", [])]
    async with _client() as c:
        try:
            async for msg in _ensure_image(c, image):
                yield dict(type="step", message=msg)
            if fetch and tc.get("fetch"):
                yield dict(type="step", message="Récupération des dépendances (réseau, sans exécuter de script)…")
                code, out, _ = await _run_container(c, image, tc["fetch"], env, archive, True, TIMEOUT)
                if code != 0:
                    yield dict(type="step", message="Dépendances : échec (les tests tenteront quand même, hors ligne).",
                               detail=out[-1500:])
            yield dict(type="step", message=f"Tests sans réseau : {command}")
            code, out, dur = await _run_container(c, image, command, env, archive, False, TIMEOUT)
        except httpx.HTTPError as e:
            yield dict(type="result", code=-1, output=f"Docker injoignable : {e.__class__.__name__}", duration=0, command=command)
            return
        except RuntimeError as e:
            yield dict(type="result", code=-1, output=str(e), duration=0, command=command)
            return
    yield dict(type="result", code=code, output=out[-12000:], duration=round(dur, 1), command=command, image=image)


async def run_text(cid: int, command: str | None, overlay: dict[str, str] | None) -> str:
    """Version pour l'agent : un texte compact (code de sortie + fin de la sortie)."""
    res = {}
    async for ev in run(cid, command, overlay):
        if ev["type"] == "result":
            res = ev
    out = res.get("output", "")
    out = re.sub(r"\x1b\[[0-9;]*m", "", out)
    head = "Tests réussis" if res.get("code") == 0 else f"Échec (code {res.get('code')})"
    return f"{head} · commande : {res.get('command')}\n{out[-4000:]}"


# ---------------------------------------------------------------- Python pour l'analyse de données

PY_IMAGE = os.getenv("ATOM_SANDBOX_IMAGE_PYTHON", "python:3.12-slim")
PY_PACKAGES = "pandas matplotlib openpyxl xlrd"


def _tar_files(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for d in ("work", "work/out", "work/data"):
            ti = tarfile.TarInfo(d); ti.type = tarfile.DIRTYPE; ti.mode = 0o777
            tar.addfile(ti)
        for name, data in files.items():
            ti = tarfile.TarInfo(f"work/{name}"); ti.size = len(data); ti.mode = 0o666
            tar.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def _untar(data: bytes) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    if not data:
        return out
    try:
        with tarfile.open(fileobj=io.BytesIO(data)) as tar:
            for m in tar.getmembers():
                if m.isfile() and m.size < 8 * 1024 * 1024:
                    f = tar.extractfile(m)
                    if f:
                        out[m.name.rsplit("/", 1)[-1]] = f.read()
    except tarfile.TarError:
        pass
    return out


async def run_python(files: dict[str, bytes], code: str, timeout: int = 180) -> tuple[int, str, dict[str, bytes]]:
    """Exécute un script Python (pandas, matplotlib) sur des fichiers, sans réseau.
    Renvoie (code de sortie, sortie, fichiers produits dans /work/out)."""
    if not enabled():
        raise RuntimeError("bac à sable " + status()["reason"])
    archive = _tar_files({**files, "analysis.py": code.encode()})
    env = ["PIP_DISABLE_PIP_VERSION_CHECK=1", "MPLBACKEND=Agg", "MPLCONFIGDIR=/tmp", "PYTHONDONTWRITEBYTECODE=1"]
    async with _client() as c:
        async for _ in _ensure_image(c, PY_IMAGE):
            pass
        # bibliothèques téléchargées une fois (cache), puis installées hors ligne
        await _run_container(c, PY_IMAGE, f"pip download -q -d /cache/pip-data {PY_PACKAGES}", env, archive, True, 600)
        cmd = (f"pip install -q --no-index --find-links /cache/pip-data {PY_PACKAGES} >/tmp/pip.log 2>&1 || "
               "(echo 'Installation des bibliothèques impossible :'; tail -5 /tmp/pip.log; exit 3); python analysis.py")
        code_, out, _ = await _run_container(c, PY_IMAGE, cmd, env, archive, False, timeout, collect="/work/out")
    produced = {}
    for k in list(_collected):
        produced.update(_untar(_collected.pop(k)))
    return code_, out, produced


async def cleanup() -> None:
    """Au démarrage : supprime les conteneurs de test restés orphelins (redémarrage pendant un test)."""
    if not enabled():
        return
    try:
        async with _client() as c:
            r = await c.get("/containers/json", params={"all": 1, "filters": json.dumps({"label": ["atom=sandbox"]})})
            for ct in r.json() if r.status_code == 200 else []:
                await c.delete(f"/containers/{ct['Id']}", params={"force": 1})
                log.info("conteneur de test orphelin supprimé : %s", ct["Id"][:12])
    except (httpx.HTTPError, ValueError):
        pass
