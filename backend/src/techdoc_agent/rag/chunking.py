"""División de documentos en fragmentos (chunks) para indexar.

Reglas (docs/05): fragmentos de ~``chunk_size`` caracteres con solape,
el encabezado de la sección como prefijo y los bloques de código nunca se
parten por la mitad. El tamaño es aproximado: un bloque atómico puede excederlo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from techdoc_agent import config
from techdoc_agent.rag.loaders import Document
from techdoc_agent.rag.store import Chunk

CODE_WINDOW = 40  # líneas por ventana en código
CODE_OVERLAP = 5  # líneas de solape entre ventanas
HUGE_CODE_FACTOR = 4  # un bloque ``` mayor que 4×chunk_size se parte en ventanas

_HEADING = re.compile(r"^(#{1,4})\s+(\S.*?)\s*$")
_PY_BOUNDARY = re.compile(r"^(?:async\s+def\s|def\s|class\s|@)")
_PY_NAME = re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+(\w+)", re.MULTILINE)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass
class _Block:
    text: str
    code: bool = False  # True si termina en un bloque ``` (no se genera solape desde él)


def _is_fence(line: str) -> bool:
    return line.lstrip().startswith("```")


# --------------------------------------------------------------------------
# Texto / Markdown
# --------------------------------------------------------------------------


def _split_sections(text: str, use_headings: bool) -> list[tuple[str, list[str]]]:
    """Devuelve ``[(línea_de_encabezado, líneas_del_cuerpo)]``; ignora encabezados dentro de ```."""
    sections: list[tuple[str, list[str]]] = [("", [])]
    in_fence = False
    for line in text.splitlines():
        if _is_fence(line):
            in_fence = not in_fence
        elif use_headings and not in_fence and _HEADING.match(line):
            sections.append((line.strip(), []))
            continue
        sections[-1][1].append(line)
    return [(h, body) for h, body in sections if "".join(body).strip()]


def _to_blocks(lines: list[str], max_merge: int) -> list[_Block]:
    """Párrafos y bloques ```; cada bloque de código se pega al párrafo que lo introduce."""
    raw: list[_Block] = []
    para: list[str] = []
    i = 0

    def flush_para() -> None:
        if para:
            raw.append(_Block("\n".join(para)))
            para.clear()

    while i < len(lines):
        line = lines[i]
        if _is_fence(line):
            flush_para()
            j = i + 1
            while j < len(lines) and not _is_fence(lines[j]):
                j += 1
            raw.append(_Block("\n".join(lines[i : j + 1]), code=True))
            i = j + 1
        elif not line.strip():
            flush_para()
            i += 1
        else:
            para.append(line)
            i += 1
    flush_para()

    blocks: list[_Block] = []
    for block in raw:
        prev = blocks[-1] if blocks else None
        if block.code and prev and not prev.code and len(prev.text) + len(block.text) <= max_merge:
            blocks[-1] = _Block(prev.text + "\n\n" + block.text, code=True)
        else:
            blocks.append(block)
    return blocks


def _split_words(text: str, size: int) -> list[str]:
    out: list[str] = []
    cur = ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > size:
            out.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        out.append(cur)
    return out


def _split_paragraph(text: str, size: int) -> list[_Block]:
    """Parte un párrafo largo por frases (y por palabras si una frase no cabe)."""
    pieces: list[str] = []
    cur = ""
    for sentence in _SENTENCE_END.split(text):
        for part in _split_words(sentence, size):
            if cur and len(cur) + 1 + len(part) > size:
                pieces.append(cur)
                cur = part
            else:
                cur = f"{cur} {part}".strip()
    if cur:
        pieces.append(cur)
    return [_Block(p) for p in pieces]


def _split_huge_code(block: str) -> list[_Block]:
    """Parte un bloque ``` gigante en ventanas de líneas, re-envolviendo cada una."""
    lines = block.splitlines()
    opener = lines[0]
    closed = len(lines) > 1 and _is_fence(lines[-1])
    inner = lines[1:-1] if closed else lines[1:]
    step = CODE_WINDOW - CODE_OVERLAP
    windows = [inner[i : i + CODE_WINDOW] for i in range(0, max(len(inner), 1), step)]
    return [_Block("\n".join([opener, *w, "```"]), code=True) for w in windows if w]


def _overlap_tail(block: _Block, overlap: int) -> str:
    """Cola del último bloque (nunca cruza bloques ni sale de código), en límite de palabra."""
    if overlap <= 0 or block.code:
        return ""
    if len(block.text) <= overlap:
        return block.text
    tail = block.text[-overlap:]
    cut = tail.find(" ")
    return tail[cut + 1 :] if cut != -1 else tail


def _pack(blocks: list[_Block], budget: int, overlap: int) -> list[str]:
    """Empaquetado voraz de bloques en fragmentos de hasta ``budget`` caracteres."""
    chunks: list[str] = []
    cur: list[_Block] = []
    has_real = False
    length = 0
    for block in blocks:
        extra = len(block.text) + (2 if cur else 0)
        if has_real and length + extra > budget:
            chunks.append("\n\n".join(b.text for b in cur))
            tail = _overlap_tail(cur[-1], overlap)
            cur = [_Block(tail)] if tail else []
            has_real = False
            length = len(tail)
            extra = len(block.text) + (2 if cur else 0)
        cur.append(block)
        has_real = True
        length += extra
    if has_real:
        chunks.append("\n\n".join(b.text for b in cur))
    return chunks


def _chunk_text(doc: Document, size: int, overlap: int) -> list[tuple[str, str]]:
    """Devuelve ``[(sección, texto)]`` para md/txt/pdf."""
    out: list[tuple[str, str]] = []
    for heading, lines in _split_sections(doc.text, use_headings=doc.doc_type == "md"):
        prefix = f"{heading}\n\n" if heading else ""
        budget = max(size - len(prefix), size // 2)
        blocks: list[_Block] = []
        for block in _to_blocks(lines, max_merge=HUGE_CODE_FACTOR * size):
            if block.code and len(block.text) > HUGE_CODE_FACTOR * size:
                blocks.extend(_split_huge_code(block.text))
            elif not block.code and len(block.text) > budget:
                # trozos más cortos que el presupuesto: así caben junto a la cola de solape
                piece_size = max(budget - overlap - 2, budget // 2)
                blocks.extend(_split_paragraph(block.text, piece_size))
            else:
                blocks.append(block)
        section = heading.lstrip("#").strip()
        out.extend((section, prefix + body) for body in _pack(blocks, budget, overlap))
    return out


# --------------------------------------------------------------------------
# Código
# --------------------------------------------------------------------------


def _windows(lines: list[str]) -> list[str]:
    step = CODE_WINDOW - CODE_OVERLAP
    return [
        "\n".join(lines[i : i + CODE_WINDOW])
        for i in range(0, max(len(lines), 1), step)
        if lines[i : i + CODE_WINDOW]
    ]


def _python_pieces(lines: list[str]) -> list[list[str]]:
    """Corta por ``def``/``class`` (y sus decoradores) en columna 0."""
    pieces: list[list[str]] = [[]]
    for line in lines:
        prev = pieces[-1][-1] if pieces[-1] else ""
        if _PY_BOUNDARY.match(line) and pieces[-1] and not prev.startswith("@"):
            pieces.append([])
        pieces[-1].append(line)
    return [p for p in pieces if "".join(p).strip()]


def _chunk_code(doc: Document, size: int) -> list[tuple[str, str]]:
    lines = doc.text.splitlines()
    if doc.metadata.get("lenguaje") != "python":
        texts = _windows(lines)
    else:
        texts = []
        cur = ""
        for piece in _python_pieces(lines):
            if len(piece) > CODE_WINDOW:
                if cur:
                    texts.append(cur)
                    cur = ""
                texts.extend(_windows(piece))
                continue
            body = "\n".join(piece)
            if cur and len(cur) + 1 + len(body) > size:
                texts.append(cur)
                cur = body
            else:
                cur = f"{cur}\n{body}" if cur else body
        if cur:
            texts.append(cur)
    out = []
    for text in texts:
        match = _PY_NAME.search(text) if doc.metadata.get("lenguaje") == "python" else None
        out.append((match.group(1) if match else "", text))
    return out


# --------------------------------------------------------------------------


def chunk_document(
    doc: Document, chunk_size: int | None = None, overlap: int | None = None
) -> list[Chunk]:
    """Divide un documento en ``Chunk`` con ids ``archivo#n`` (n desde 0)."""
    size = chunk_size if chunk_size is not None else config.settings.chunk_size
    ovl = overlap if overlap is not None else config.settings.chunk_overlap
    pieces = _chunk_code(doc, size) if doc.doc_type == "code" else _chunk_text(doc, size, ovl)

    chunks = []
    for index, (section, text) in enumerate(pieces):
        metadata = {"chunk_index": index, "section": section, "type": doc.doc_type, **doc.metadata}
        chunks.append(Chunk(f"{doc.source}#{index}", doc.source, text, metadata))
    return chunks
