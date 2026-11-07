"""Extraction et découpage du texte : PDF, Office, texte, images (OCR), code.

Fonctions pures, sans base de données : utilisées par la bibliothèque et les pièces jointes.
"""

from __future__ import annotations

import io
import re
import zipfile

from . import ocr

CHUNK, OVERLAP = 1100, 180          # documents : caractères
CODE_LINES, CODE_OVERLAP = 60, 8     # code : lignes


class Unsupported(ValueError):
    pass


def extract_pages(name: str, raw: bytes) -> list[tuple[int | None, str]]:
    """[(page, texte)] — page = None pour les formats sans pagination."""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext == "pdf" or raw[:5] == b"%PDF-":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw))
        allp = [(i + 1, (p.extract_text() or "").strip()) for i, p in enumerate(reader.pages[:2000])]
        # Pages scannées (pas ou presque pas de texte) : lecture par OCR.
        scanned = {n for n, t in allp if len(t) < 40}
        if scanned and ocr.pdf_available():
            got = dict(ocr.pdf_pages(raw, only=scanned))
            allp = [(n, got.get(n, t)) for n, t in allp]
        pages = [p for p in allp if p[1]]
        if not pages:
            raise Unsupported("PDF sans texte (document scanné ?) et lecture des scans indisponible sur ce serveur."
                              if not ocr.pdf_available() else "Aucun texte lisible, même par OCR.")
        return pages
    if ext == "docx":
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if z.getinfo("word/document.xml").file_size > 40 * 1024 * 1024:   # archive piégée (« zip bomb »)
                raise Unsupported("Document trop volumineux une fois décompressé.")
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
        xml = re.sub(r"</w:p>", "\n", xml)
        xml = re.sub(r"<w:tab/>", "\t", xml)
        text = re.sub(r"<[^>]+>", "", xml)
        import html as _h
        return [(None, _h.unescape(text).strip())]
    if ext in {"odt"}:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if z.getinfo("content.xml").file_size > 40 * 1024 * 1024:
                raise Unsupported("Document trop volumineux une fois décompressé.")
            xml = z.read("content.xml").decode("utf-8", "ignore")
        xml = re.sub(r"</text:p>|</text:h>", "\n", xml)
        import html as _h
        return [(None, _h.unescape(re.sub(r"<[^>]+>", "", xml)).strip())]
    if ext in ocr.IMAGE_EXT:
        if not ocr.available():
            raise Unsupported("Lecture des images (OCR) indisponible sur ce serveur.")
        text = ocr.image_text(raw, ext)
        if not text:
            raise Unsupported("Aucun texte trouvé dans l'image.")
        return [(None, text)]
    if ext == "heic":
        raise Unsupported("Format HEIC non pris en charge : exporte l'image en JPEG.")
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if "\x00" in text[:4000]:
        raise Unsupported("Format non pris en charge (fichier binaire).")
    if ext in {"html", "htm"}:
        from .search import page_text
        text = page_text(text, limit=2_000_000)
    return [(None, text)]


def chunk_text(pages: list[tuple[int | None, str]]) -> list[dict]:
    out = []
    for page, text in pages:
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        i = 0
        while i < len(text):
            end = min(len(text), i + CHUNK)
            if end < len(text):   # couper sur une fin de paragraphe ou de phrase si possible
                cut = max(text.rfind("\n\n", i + CHUNK // 2, end), text.rfind(". ", i + CHUNK // 2, end))
                if cut > i:
                    end = cut + 1
            piece = text[i:end].strip()
            if piece:
                out.append({"page": page, "text": piece})
            if end >= len(text):
                break
            i = max(end - OVERLAP, i + 1)
    return out


def chunk_code(path: str, text: str) -> list[dict]:
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        j = min(len(lines), i + CODE_LINES)
        body = "\n".join(lines[i:j]).strip()
        if body:
            out.append({"line_start": i + 1, "line_end": j, "text": f"# {path} (lignes {i + 1}-{j})\n{body}"})
        if j >= len(lines):
            break
        i = j - CODE_OVERLAP
    return out
