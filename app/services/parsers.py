from __future__ import annotations

import io
import re
from pathlib import Path

from docx import Document
from pypdf import PdfReader

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".markdown"}


class ParseError(ValueError):
    pass


def parse_upload(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ParseError(f"Unsupported file type: {ext or 'none'}")
    if ext == ".pdf":
        text = _parse_pdf(data)
    elif ext == ".docx":
        text = _parse_docx(data)
    else:
        text = _parse_text(data, markdown=ext in {".md", ".markdown"})

    text = text.strip()
    if not text:
        raise ParseError("No readable text found in this file.")
    return text


def _parse_pdf(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:
        raise ParseError("Could not read this PDF.") from exc

    if reader.is_encrypted:
        try:
            if not reader.decrypt(""):
                raise ParseError("This PDF is encrypted and cannot be read.")
        except ParseError:
            raise
        except Exception as exc:
            raise ParseError("This PDF is encrypted and cannot be read.") from exc

    pages: list[tuple[int, str]] = []
    try:
        for index, page in enumerate(reader.pages, start=1):
            pages.append((index, (page.extract_text() or "").strip()))
    except Exception as exc:
        raise ParseError("Could not extract text from this PDF.") from exc

    if not any(text for _, text in pages):
        raise ParseError(
            "No text layer found. Scanned PDFs are not supported; "
            "please upload a text-based PDF, DOCX, TXT, or Markdown file."
        )

    return "\n\n".join(f"[[PAGE {index}]]\n{text}" for index, text in pages)


def _parse_docx(data: bytes) -> str:
    try:
        document = Document(io.BytesIO(data))
    except Exception as exc:
        raise ParseError("Could not read this DOCX file.") from exc

    lines: list[str] = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        style = (paragraph.style.name if paragraph.style else "") or ""
        if style.lower().startswith("heading"):
            lines.append(f"[[SECTION: {text}]]")
        else:
            lines.append(text)

    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                lines.append(" | ".join(cells))

    result = "\n".join(lines).strip()
    if not result:
        raise ParseError("No readable text found in this DOCX file.")
    return result


def _parse_text(data: bytes, *, markdown: bool) -> str:
    text = _decode_text(data)
    if markdown:
        text = _normalize_markdown(text)
    return text


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ParseError("Could not decode this text file.")


def _normalize_markdown(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        heading = re.match(r"^\s{0,3}(#{1,6})\s+(.*)$", line)
        if heading:
            lines.append(f"[[SECTION: {heading.group(2).strip()}]]")
            continue
        line = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", line)
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
        line = re.sub(r"[*_`>#]+", "", line)
        lines.append(line)
    return "\n".join(lines)
