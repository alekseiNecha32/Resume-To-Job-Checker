from io import BytesIO
from typing import Literal, Optional
from pdfminer.high_level import extract_text as pdf_extract
from docx import Document

Allowed = Literal["pdf", "docx", "txt"]

def sniff_ext(filename: str) -> Optional[Allowed]:
    name = (filename or "").lower()
    if name.endswith(".pdf"): return "pdf"
    if name.endswith(".docx"): return "docx"
    if name.endswith(".txt"): return "txt"
    return None

def extract_from_pdf(file_bytes: bytes) -> str:
    bio = BytesIO(file_bytes)
    return (pdf_extract(bio) or "").strip()

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
