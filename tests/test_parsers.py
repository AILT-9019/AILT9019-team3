import io

import pytest
from docx import Document
from pypdf import PdfWriter
from reportlab.pdfgen import canvas

from app.services.parsers import ParseError, parse_upload


def test_parse_txt_utf8():
    text = parse_upload("notice.txt", b"Assignment 1 is due on 24 October 2026.")
    assert "Assignment 1" in text


def test_parse_txt_gb18030():
    text = parse_upload("notice.txt", "作业截止日期".encode("gb18030"))
    assert text == "作业截止日期"


def test_parse_markdown_keeps_sections_and_strips_markup():
    raw = b"# Assessment\n\n**Assignment 1** is due [24 Oct](https://example.com).\n"
    text = parse_upload("syllabus.md", raw)
    assert "[[SECTION: Assessment]]" in text
    assert "Assignment 1" in text
    assert "**" not in text
    assert "https://example.com" not in text


def test_parse_docx_keeps_heading_and_body():
    document = Document()
    document.add_heading("Assessment", level=1)
    document.add_paragraph("Assignment 1 is due on 24 October 2026.")
    buffer = io.BytesIO()
    document.save(buffer)

    text = parse_upload("syllabus.docx", buffer.getvalue())
    assert "[[SECTION: Assessment]]" in text
    assert "Assignment 1 is due" in text


def test_parse_text_pdf_keeps_page_marker():
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 720, "Assignment 1 is due on 24 October 2026.")
    pdf.save()

    text = parse_upload("syllabus.pdf", buffer.getvalue())
    assert "[[PAGE 1]]" in text
    assert "Assignment 1 is due" in text


def test_parse_blank_pdf_reports_no_text_layer():
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buffer = io.BytesIO()
    writer.write(buffer)

    with pytest.raises(ParseError, match="No text layer"):
        parse_upload("scanned.pdf", buffer.getvalue())


def test_parse_unsupported_extension():
    with pytest.raises(ParseError, match="Unsupported file type"):
        parse_upload("malware.exe", b"hello")


def test_parse_empty_text():
    with pytest.raises(ParseError, match="No readable text"):
        parse_upload("empty.txt", b"   \n")
