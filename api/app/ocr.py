"""Lecture des scans (OCR) : PDF sans texte et images, avec Tesseract.

Tout reste sur le serveur. Nécessite tesseract-ocr (+ langue fra) et poppler-utils (pdftoppm),
installés dans l'image Docker. Sans eux, available() renvoie False et l'appelant prévient.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

LANGS = os.getenv("ATOM_OCR_LANGS", "fra+eng")
DPI = int(os.getenv("ATOM_OCR_DPI", "200"))
IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp", "bmp", "tif", "tiff"}


def available() -> bool:
    return bool(shutil.which("tesseract"))


def pdf_available() -> bool:
    return available() and bool(shutil.which("pdftoppm"))


def _tesseract(path: str) -> str:
    r = subprocess.run(["tesseract", path, "stdout", "-l", LANGS, "--psm", "3"],
                       capture_output=True, timeout=180, check=False)
    if r.returncode != 0:
        # langue absente : on retente en anglais seul plutôt que d'échouer
        r = subprocess.run(["tesseract", path, "stdout"], capture_output=True, timeout=180, check=False)
    return r.stdout.decode("utf-8", "ignore").strip()


def image_text(raw: bytes, ext: str = "png") -> str:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / f"img.{ext or 'png'}"
        p.write_bytes(raw)
        return _tesseract(str(p))


def pdf_pages(raw: bytes, max_pages: int = 300, only: set[int] | None = None) -> list[tuple[int, str]]:
    """[(page, texte)] pour les pages d'un PDF scanné (only = numéros de page à traiter, 1-based)."""
    out = []
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "doc.pdf"
        src.write_bytes(raw)
        pages = sorted(only) if only else range(1, max_pages + 1)
        for n in pages:
            if n > max_pages:
                break
            base = Path(d) / f"p{n}"
            r = subprocess.run(["pdftoppm", "-r", str(DPI), "-gray", "-png", "-f", str(n), "-l", str(n), "-singlefile",
                                str(src), str(base)], capture_output=True, timeout=120, check=False)
            img = base.with_suffix(".png")
            if r.returncode != 0 or not img.exists():
                if only is None:
                    break   # au-delà de la dernière page
                continue
            text = _tesseract(str(img))
            img.unlink(missing_ok=True)
            if text:
                out.append((n, text))
    return out
