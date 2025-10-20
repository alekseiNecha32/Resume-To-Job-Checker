# app/blueprints/api.py
from flask import Blueprint, request, jsonify
from werkzeug.exceptions import BadRequest
from app.utils.extractors import extract_any, sniff_ext
import re  # <-- needed

api_bp = Blueprint("api", __name__)

@api_bp.get("/ping")
def ping():
    return jsonify({"message": "pong"}), 200

# ---------- Simple ATS scoring helpers ----------
MAX_SIZE = 5 * 1024 * 1024  # 5MB

STOPWORDS = {
    "a","an","the","and","or","to","of","in","on","for","with","at","by","from",
    "is","are","was","were","be","as","that","this","it","its","your","you","we",
    "our","their","they","he","she","i"
}

def normalize(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z+\-.#/]*", text.lower())
    return [w for w in words if len(w) >= 2 and w not in STOPWORDS]

def ats_score(resume_text: str, job_text: str) -> tuple[int, list[str]]:
    resume_tokens = set(normalize(resume_text))
    job_tokens    = set(normalize(job_text))
    if not job_tokens:
        return 0, []
    matches = sorted(job_tokens & resume_tokens)
    score = round(100 * len(matches) / len(job_tokens))
    return score, matches

# ---------- Extract only: return plain text for preview ----------
@api_bp.post("/extract")
def extract_file():
    if "file" not in request.files:
        raise BadRequest("No file provided")

    file = request.files["file"]
    if not file.filename:
        raise BadRequest("Empty filename")

    if sniff_ext(file.filename) is None:
        raise BadRequest("Unsupported file type. Use PDF, DOCX, or TXT.")

    file_bytes = file.read()
    if len(file_bytes) > MAX_SIZE:
        return jsonify({"detail": "File too large (5MB limit)."}), 413

    try:
        resume_text = extract_any(file.filename, file_bytes)
        if not resume_text.strip():
            raise BadRequest("Could not read any text from the file.")
    except Exception as e:
        return jsonify({"detail": f"Extraction failed: {e}"}), 400

    # Return the raw text so the frontend can display it
    return jsonify({
        "text": resume_text,
        "resume_chars": len(resume_text),
    }), 200

# ---------- Score only: return ATS score (and optional matches) ----------
@api_bp.post("/score")
def score():
    data = request.get_json(silent=True) or {}
    resume_text = data.get("resume_text", "")
    job_text    = data.get("job_text", "")
    if not resume_text or not job_text:
        raise BadRequest("resume_text and job_text are required.")

    score_pct, matches = ats_score(resume_text, job_text)
    return jsonify({
        "score": score_pct,
        "matches": matches,  
    }), 200
