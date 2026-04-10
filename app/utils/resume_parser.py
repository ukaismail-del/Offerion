import os

import pdfplumber
from docx import Document

PREVIEW_LIMIT = 2000


def get_file_extension(filename):
    return filename.rsplit(".", 1)[1].lower() if "." in filename else ""


def extract_text(filepath):
    """Extract text from a resume file. Returns (text, error)."""
    ext = get_file_extension(filepath)

    if ext == "pdf":
        return _extract_pdf(filepath)
    elif ext == "docx":
        return _extract_docx(filepath)
    elif ext == "doc":
        return "", ".doc files are not supported yet. Please convert to .docx or .pdf."
    else:
        return "", f"Unsupported file type: .{ext}"


def _extract_pdf(filepath):
    try:
        text = ""
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        if not text.strip():
            return "", "No readable text found in this PDF."
        return text.strip(), None
    except Exception as e:
        return "", f"Error reading PDF: {e}"


def _extract_docx(filepath):
    try:
        doc = Document(filepath)
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        if not text.strip():
            return "", "No readable text found in this DOCX."
        return text.strip(), None
    except Exception as e:
        return "", f"Error reading DOCX: {e}"


def preview_text(text):
    """Return a truncated preview of extracted text."""
    if len(text) <= PREVIEW_LIMIT:
        return text
    return text[:PREVIEW_LIMIT] + "\n\n[... preview truncated ...]"
