"""Tests del chunking (sin modelos)."""

from pathlib import Path

from techdoc_agent.rag.chunking import chunk_document
from techdoc_agent.rag.loaders import Document, load_file

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "sample_docs" / "taskflow.md"


def md(text: str, source: str = "doc.md") -> Document:
    return Document(source, text, "md")


def fences(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.lstrip().startswith("```"))


def test_splits_by_headings_and_prefixes_section() -> None:
    chunks = chunk_document(md("# Uno\ntexto uno\n\n## Dos\ntexto dos\n"), 700, 100)
    assert [c.metadata["section"] for c in chunks] == ["Uno", "Dos"]
    assert chunks[0].text == "# Uno\n\ntexto uno"
    assert chunks[1].text.startswith("## Dos\n\n")


def test_ids_and_metadata() -> None:
    chunks = chunk_document(md("# A\nx\n\n# B\ny"), 700, 100)
    assert [c.id for c in chunks] == ["doc.md#0", "doc.md#1"]
    assert chunks[1].source == "doc.md"
    assert chunks[1].metadata == {"chunk_index": 1, "section": "B", "type": "md"}


def test_text_before_first_heading_has_empty_section() -> None:
    chunks = chunk_document(md("intro sin título\n\n# A\nx"), 700, 100)
    assert chunks[0].metadata["section"] == "" and chunks[0].text == "intro sin título"


def test_heading_inside_code_block_is_not_a_section() -> None:
    text = "# Real\nintro:\n\n```bash\n# comentario, no encabezado\nls\n```\n"
    chunks = chunk_document(md(text), 700, 100)
    assert len(chunks) == 1 and "# comentario" in chunks[0].text


def test_empty_sections_are_skipped() -> None:
    chunks = chunk_document(md("# Vacío\n\n## Con texto\nhola"), 700, 100)
    assert [c.metadata["section"] for c in chunks] == ["Con texto"]


def test_code_block_is_never_split() -> None:
    code = "\n".join(f"    linea_{i} = {i}" for i in range(25))
    text = f"# Sec\nPárrafo uno.\n\n```python\n{code}\n```\n\nPárrafo dos que sigue.\n"
    for chunk in chunk_document(md(text), 120, 20):
        assert fences(chunk.text) % 2 == 0, chunk.text


def test_code_block_stays_with_introducing_paragraph() -> None:
    text = "# Sec\nRelleno " + "x" * 80 + "\n\nAsí se usa:\n\n```python\ncola.run()\n```\n"
    chunks = chunk_document(md(text), 120, 0)
    with_code = next(c for c in chunks if "cola.run()" in c.text)
    assert "Así se usa:" in with_code.text


def test_huge_code_block_is_windowed_and_rewrapped() -> None:
    code = "\n".join(f"x{i} = {i}" for i in range(200))
    chunks = chunk_document(md(f"# G\n```python\n{code}\n```\n"), 100, 20)
    assert len(chunks) > 1
    for chunk in chunks:
        assert fences(chunk.text) == 2 and "```python" in chunk.text


def test_long_paragraph_is_split_with_overlap() -> None:
    sentences = [f"Esta es la frase número {i} del párrafo largo." for i in range(30)]
    chunks = chunk_document(md("# L\n" + " ".join(sentences)), 200, 40)
    assert len(chunks) > 3
    for prev, nxt in zip(chunks, chunks[1:], strict=False):
        prev_body = prev.text.split("\n\n", 1)[1]
        nxt_body = nxt.text.split("\n\n", 1)[1]
        # el inicio del siguiente repite la cola del anterior (solape ≤ 40 caracteres)
        head = nxt_body[:15]
        assert head in prev_body[-60:], (prev_body, nxt_body)
    assert all(len(c.text) <= 200 for c in chunks)


def test_no_overlap_after_a_code_block() -> None:
    text = "# S\nIntro:\n\n```python\nprint('a')\n```\n\n" + "palabra " * 60
    chunks = chunk_document(md(text), 100, 30)
    second = chunks[1].text.split("\n\n", 1)[1]
    assert "print('a')" not in second and fences(second) == 0


def test_plain_text_has_no_sections() -> None:
    doc = Document("n.txt", "# no es encabezado\n\nsegundo párrafo", "txt")
    chunks = chunk_document(doc, 700, 100)
    assert len(chunks) == 1 and chunks[0].metadata["section"] == ""
    assert chunks[0].text.startswith("# no es encabezado")


def test_python_is_split_by_functions() -> None:
    body = "    x = 1\n" * 6
    source = f"import os\n\n\ndef a():\n{body}\n\n@decorador\ndef b():\n{body}\n\nclass C:\n{body}"
    doc = Document("m.py", source, "code", {"lenguaje": "python"})
    chunks = chunk_document(doc, 90, 0)
    names = [c.metadata["section"] for c in chunks]
    assert "a" in names and "b" in names and "C" in names
    decorated = next(c for c in chunks if "def b" in c.text)
    assert "@decorador" in decorated.text  # el decorador viaja con su función
    assert all(c.metadata["lenguaje"] == "python" for c in chunks)


def test_long_code_uses_overlapping_windows() -> None:
    source = "\n".join(f"linea {i}" for i in range(100))
    doc = Document("a.js", source, "code", {"lenguaje": "javascript"})
    chunks = chunk_document(doc, 700, 100)
    assert len(chunks) == 3  # ventanas de 40 líneas, avance de 35
    first_lines = chunks[0].text.splitlines()
    second_lines = chunks[1].text.splitlines()
    assert first_lines[-5:] == second_lines[:5]


def test_sample_document_retries_section() -> None:
    chunks = chunk_document(load_file(SAMPLE))
    retries = [c for c in chunks if "max_retries" in c.text]
    assert retries and all(c.metadata["section"] == "Reintentos" for c in retries)
    assert all(fences(c.text) % 2 == 0 for c in chunks)
    assert {"Instalación", "Workers", "Errores comunes"} <= {c.metadata["section"] for c in chunks}


def test_empty_document_has_no_chunks() -> None:
    assert chunk_document(md("   \n\n"), 700, 100) == []
