from flask import Blueprint, request, jsonify
from werkzeug.exceptions import BadRequest
from app.utils.extractors import extract_any, sniff_ext
import re

from app.utils.text_utils import get_text_similarity

api_bp = Blueprint("api", __name__, url_prefix="/api")

@api_bp.get("/ping")
def ping():
    return jsonify({"message": "pong"}), 200

MAX_SIZE = 5 * 1024 * 1024  # 5MB

STOPWORDS = {
    "a","an","the","and","or","to","of","in","on","for","with","at","by","from",
    "is","are","was","were","be","as","that","this","it","its","your","you","we",
    "our","their","they","he","she","i"
}

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


# ---------- helper to coerce any shape → string ----------
def _as_text(v):
    """Coerce incoming values to a plain string (handles dicts like {'text': '...'})."""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        for k in ("text", "value", "content"):
            if isinstance(v.get(k), str):
                return v[k]
        return ""
    if isinstance(v, (list, tuple)):
        return " ".join(x for x in v if isinstance(x, str))
    return str(v or "")


@api_bp.route("/score", methods=["POST", "OPTIONS"])
def score_resume_to_job():
    if request.method == "OPTIONS":
        return ("", 204)

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Expected JSON body with resumeText and jobText."}), 400

    # 1) Coerce to strings, THEN strip
    resume_text = _as_text(data.get("resumeText")).strip()
    job_text    = _as_text(data.get("jobText")).strip()

    missing = []
    if not resume_text:
        missing.append("resumeText")
    if not job_text:
        missing.append("jobText")
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    # 2) Cap extreme sizes BEFORE embedding
    MAX_CHARS = 20000
    if len(resume_text) > MAX_CHARS:
        resume_text = resume_text[:MAX_CHARS]
    if len(job_text) > MAX_CHARS:
        job_text = job_text[:MAX_CHARS]

    # 3) Wrap scoring so any error returns JSON (not HTML 500)
    try:
        sim = get_text_similarity(resume_text, job_text)
        return jsonify({
            "similarity": round(sim, 4),
            "model": "sentence-transformers/all-MiniLM-L6-v2"
        }), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Internal error while scoring: {type(e).__name__}"}), 500