"""Tests de los loaders (sin red ni modelos)."""

from pathlib import Path

import pytest
from pypdf import PdfWriter

from techdoc_agent.rag.loaders import load_file

# PDF mínimo con una página y el texto "Hola PDF" (pypdf reconstruye la tabla xref).
MINIMAL_PDF = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length 44>>stream
BT /F1 18 Tf 20 100 Td (Hola PDF) Tj ET
endstream
endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
trailer<</Root 1 0 R/Size 6>>
startxref
0
%%EOF
"""


def write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_markdown_and_txt(tmp_path: Path) -> None:
    md = load_file(write(tmp_path, "guia.md", "# Título\ntexto"))
    assert (md.source, md.doc_type, md.text) == ("guia.md", "md", "# Título\ntexto")
    assert load_file(write(tmp_path, "notas.txt", "hola")).doc_type == "txt"


@pytest.mark.parametrize(
    ("name", "lang"),
    [("a.py", "python"), ("a.js", "javascript"), ("a.ts", "typescript"),
     ("A.java", "java"), ("a.json", "json"), ("a.yaml", "yaml"), ("a.yml", "yaml")],
)
def test_code_files_carry_language(tmp_path: Path, name: str, lang: str) -> None:
    doc = load_file(write(tmp_path, name, "x"))
    assert doc.doc_type == "code" and doc.metadata["lenguaje"] == lang


def test_extension_is_case_insensitive(tmp_path: Path) -> None:
    assert load_file(write(tmp_path, "README.MD", "x")).doc_type == "md"


@pytest.mark.parametrize("name", ["virus.exe", "script.sh", "sin_extension"])
def test_disallowed_extension_rejected(tmp_path: Path, name: str) -> None:
    with pytest.raises(ValueError, match="Extensión no permitida"):
        load_file(write(tmp_path, name, "x"))


def test_too_large_file_rejected(tmp_path: Path) -> None:
    path = write(tmp_path, "grande.txt", "x" * 2048)
    with pytest.raises(ValueError, match="tamaño máximo"):
        load_file(path, max_mb=1 / 1024)  # 1 KB
    assert load_file(path, max_mb=1).text  # dentro del límite sí


def test_directory_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "carpeta.md").mkdir()
    with pytest.raises(ValueError, match="No es un archivo"):
        load_file(tmp_path / "carpeta.md")


def test_pdf_with_text(tmp_path: Path) -> None:
    path = tmp_path / "doc.pdf"
    path.write_bytes(MINIMAL_PDF)
    doc = load_file(path)
    assert doc.doc_type == "pdf" and "Hola PDF" in doc.text and doc.warnings == []


def test_pdf_without_text_warns(tmp_path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    path = tmp_path / "escaneado.pdf"
    with path.open("wb") as fh:
        writer.write(fh)
    doc = load_file(path)
    assert doc.text == "" and "no contiene texto" in doc.warnings[0]


def test_invalid_utf8_is_replaced_not_fatal(tmp_path: Path) -> None:
    path = tmp_path / "raro.txt"
    path.write_bytes(b"caf\xe9 ok")
    assert "ok" in load_file(path).text


def test_corrupt_pdf_is_value_error(tmp_path: Path) -> None:
    path = tmp_path / "roto.pdf"
    path.write_bytes(b"esto no es un pdf")
    with pytest.raises(ValueError, match="No se pudo leer el PDF"):
        load_file(path)
