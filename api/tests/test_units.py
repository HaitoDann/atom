import random


def test_command_filter_any_split():
    from app.reminders import CommandFilter

    s = "[joy] Ok demain. [[rappel 2030-01-02T09:00 | Garage]] Et [[pas une cmd]] [x]"
    for _ in range(100):
        f, out, i = CommandFilter(), "", 0
        while i < len(s):
            k = random.randint(1, 6)
            out += f.feed(s[i:i + k])
            i += k
        out += f.flush()
        assert out == "[joy] Ok demain.  Et [[pas une cmd]] [x]"
        assert f.commands == [("rappel", "2030-01-02T09:00 | Garage")]


def test_reminder_dates():
    from app import reminders

    assert reminders.parse_due("2030-01-02T09:00") is not None
    assert reminders.parse_due("pas une date") is None
    ev = reminders.execute("rappel", "2000-01-01T09:00 | Trop tard", None)
    assert ev["action"] == "error"


def test_chunking():
    from app.library import chunk_code, chunk_text

    text = ("Une phrase assez longue pour remplir le passage. " * 60).strip()
    chunks = chunk_text([(1, text)])
    assert len(chunks) > 1 and all(len(c["text"]) <= 1200 for c in chunks) and chunks[0]["page"] == 1
    code = "\n".join(f"line {i}" for i in range(150))
    cc = chunk_code("a.py", code)
    assert cc[0]["line_start"] == 1 and cc[-1]["line_end"] == 150


def test_extract_docx_and_binary():
    import io
    import zipfile

    import pytest
    from app.library import Unsupported, extract_pages

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", "<w:p><w:t>Bonjour</w:t></w:p><w:p><w:t>Monde</w:t></w:p>")
    assert extract_pages("note.docx", buf.getvalue())[0][1].split() == ["Bonjour", "Monde"]
    with pytest.raises(Unsupported):
        extract_pages("photo.png", b"\x89PNG")


def test_memory_worth_extracting():
    from app.memory import worth_extracting

    assert not worth_extracting("2+2")
    assert not worth_extracting("merci beaucoup")
    assert worth_extracting("Je travaille sur un projet de NAS")
