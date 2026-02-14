import re
from io import BytesIO
from typing import Literal, Optional
import pymupdf
from docx import Document

Allowed = Literal["pdf", "docx", "txt"]

def sniff_ext(filename: str) -> Optional[Allowed]:
    name = (filename or "").lower()
    if name.endswith(".pdf"): return "pdf"
    if name.endswith(".docx"): return "docx"
    if name.endswith(".txt"): return "txt"
    return None

_INVISIBLE_RE = re.compile(
    r'[\u200b\u200c\u200d\u200e\u200f\u00ad\ufeff\u2060\u00a0\u2000-\u200a\u202f\u205f\u3000\x0c]'
)

def _clean_line(line: str) -> str:
    """Strip whitespace and invisible Unicode characters."""
    return _INVISIBLE_RE.sub('', line).strip()

def _collapse_blank_lines(text: str) -> str:
    """Normalize line endings, remove invisible chars, allow at most one blank line."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    result = []
    prev_empty = False
    for line in text.split("\n"):
        cleaned = _clean_line(line)
        if not cleaned:
            if not prev_empty:
                result.append("")
            prev_empty = True
        else:
            result.append(cleaned)
            prev_empty = False
    return "\n".join(result)

def extract_from_pdf(file_bytes: bytes) -> str:
    doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return _collapse_blank_lines(text).strip()

def extract_from_docx(file_bytes: bytes) -> str:
    bio = BytesIO(file_bytes)
    doc = Document(bio)
    return "\n".join(p.text for p in doc.paragraphs).strip()

def extract_from_txt(file_bytes: bytes, encoding="utf-8") -> str:
    return file_bytes.decode(encoding, errors="ignore").strip()

def extract_any(filename: str, file_bytes: bytes) -> str:
    kind = sniff_ext(filename)
    if kind == "pdf":  return extract_from_pdf(file_bytes)
    if kind == "docx": return extract_from_docx(file_bytes)
    if kind == "txt":  return extract_from_txt(file_bytes)
    raise ValueError("Unsupported file type. Use PDF, DOCX, or TXT.")
