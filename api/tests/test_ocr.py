import io

import pytest

from app import library, ocr

pytestmark = pytest.mark.skipif(not ocr.pdf_available(), reason="tesseract/pdftoppm absents")


def _img():
    from PIL import Image, ImageDraw, ImageFont
    im = Image.new("L", (1200, 300), 255)
    try:
        f = ImageFont.truetype("DejaVuSans.ttf", 48)
    except OSError:
        f = ImageFont.load_default(size=48)
    ImageDraw.Draw(im).text((40, 100), "Facture numero 42", fill=0, font=f)
    return im


def test_image_and_scanned_pdf():
    pytest.importorskip("PIL")
    im = _img()
    png, pdf = io.BytesIO(), io.BytesIO()
    im.save(png, "PNG"); im.convert("RGB").save(pdf, "PDF")
    assert "42" in library.extract_pages("a.png", png.getvalue())[0][1]
    pages = library.extract_pages("a.pdf", pdf.getvalue())
    assert pages[0][0] == 1 and "Facture" in pages[0][1]
