from flask import Blueprint, request, jsonify
from werkzeug.exceptions import BadRequest
from app.utils.extractors import extract_any, sniff_ext

from sentence_transformers import SentenceTransformer, util

# from app.utils.text_utils import get_text_similarity
_SBERT = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
_ = _SBERT.encode("warmup", convert_to_tensor=True, normalize_embeddings=True)

api_bp = Blueprint("api", __name__, url_prefix="/api")

@api_bp.get("/ping")
def ping():
    return jsonify({"message": "pong"}), 200

MAX_SIZE = 5 * 1024 * 1024  

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

    return jsonify({
        "text": resume_text,
        "resume_chars": len(resume_text),
    }), 200


# ---------- helper to coerce any shape → string ----------
def _as_text(v):
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

    data = request.get_json(silent=True) or {}

    resume_text = _as_text(data.get("resumeText") or data.get("resume_text")).strip()
    job_text    = _as_text(data.get("jobText")   or data.get("job_text")).strip()

    if not resume_text or not job_text:
        return jsonify({"error": "Missing fields: resumeText, jobText"}), 400

    MAX_CHARS = 20000
    if len(resume_text) > MAX_CHARS: resume_text = resume_text[:MAX_CHARS]
    if len(job_text)    > MAX_CHARS: job_text    = job_text[:MAX_CHARS]

    # ---- Existing SBERT similarity logic ----
    emb_resume = _SBERT.encode(resume_text, convert_to_tensor=True, normalize_embeddings=True)
    emb_job    = _SBERT.encode(job_text,    convert_to_tensor=True, normalize_embeddings=True)
    similarity = float(util.cos_sim(emb_resume, emb_job).item())

    shared = len(set(resume_text.split()) & set(job_text.split()))
    penalty = 0.15 if shared < 5 else 0.0
    adjusted = max(similarity - penalty, 0.0)
    score = round(adjusted * 100)

    # ---- NEW: matching & missing keywords ----
    import re
    from collections import Counter

    def tokenize(text):
        return re.findall(r"[A-Za-z0-9][A-Za-z0-9.+#/-]*", text.lower())

    tokens_resume = set(tokenize(resume_text))
    tokens_job = [t for t in tokenize(job_text) if t not in STOPWORDS]
    freq_job = Counter(tokens_job)
    # choose top keywords from job description (up to 20)
    job_keywords = [w for w, _ in freq_job.most_common(20)]

    matched = [kw for kw in job_keywords if kw in tokens_resume]
    missing = [kw for kw in job_keywords if kw not in tokens_resume]

    # ---- Final response ----
    return jsonify({
        "model": "sentence-transformers/all-MiniLM-L6-v2",
        "similarity": round(similarity, 4),
        "score": score,
        "matchedKeywords": matched,
        "missingKeywords": missing
    }), 200
