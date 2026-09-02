"""Extract text from a PDF. Digital PDFs only; scanned PDFs need OCR (out of scope for v1, see README)."""

from pathlib import Path

from pypdf import PdfReader


def pdf_to_text(path: str | Path) -> str:
    reader = PdfReader(str(path))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    if len(text.strip()) < 40:
        raise ValueError(f"{path}: almost no text layer; likely a scanned PDF (needs OCR)")
    return text
