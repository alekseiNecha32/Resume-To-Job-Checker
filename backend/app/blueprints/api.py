from flask import Blueprint, request, jsonify
from werkzeug.exceptions import BadRequest
from app.utils.extractors import extract_any, sniff_ext

api_bp = Blueprint("api", __name__)

@api_bp.get("/ping")
def ping():
    return jsonify({"message": "pong"}), 200

# TODO: import your real scoring function:
# from app.services.scoring import score_resume_core
def score_resume_core(resume_text: str, job_text: str, job_title=None, is_pro=False) -> dict:
    # stub; replace with your real scoring call/logic
    return {
        "text": resume_text, 
        "resume_chars": len(resume_text),
        "job_chars": len(job_text),
        "score": None,
        "matches": [],
    }

MAX_SIZE = 5 * 1024 * 1024  # 5MB


# STOPWORDS = {
#     "a","an","the","and","or","to","of","in","on","for","with","at","by","from",
#     "is","are","was","were","be","as","that","this","it","its","your","you","we",
#     "our","their","they","he","she","i"
# }

# def normalize(text: str) -> list[str]:
#     # simple keyword extractor: words >= 2 chars, lowercased, no stopwords
#     words = re.findall(r"[a-zA-Z][a-zA-Z+\-.#/]*", text.lower())
#     return [w for w in words if len(w) >= 2 and w not in STOPWORDS]

# def ats_score(resume_text: str, job_text: str) -> tuple[int, list[str]]:
#     resume_tokens = set(normalize(resume_text))
#     job_tokens    = set(normalize(job_text))
#     if not job_tokens:
#         return 0, []
#     matches = sorted(job_tokens & resume_tokens)
#     score = round(100 * len(matches) / len(job_tokens))
#     return score, matches


@api_bp.post("/extract")  
def extract_file():
    """
    Upload PDF/DOCX/TXT + job_text and get a scored response.
    Frontend sends multipart/form-data: file, job_text, job_title?, isPro?
    """
    if "file" not in request.files:
        raise BadRequest("No file provided")

    file = request.files["file"]
    job_text = request.form.get("job_text", "")
    job_title = request.form.get("job_title") or None
    is_pro = (request.form.get("isPro", "false").lower() == "true")

    if not file.filename:
        raise BadRequest("Empty filename")

    ext = sniff_ext(file.filename)
    if ext is None:
        raise BadRequest("Unsupported file type. Use PDF, DOCX, or TXT.")

    # optional size guard
    file_bytes = file.read()
    if len(file_bytes) > MAX_SIZE:
        return jsonify({"detail": "File too large (5MB limit)."}), 413

    try:
        resume_text = extract_any(file.filename, file_bytes)
        if not resume_text:
            raise BadRequest("Could not read any text from the file.")
    except Exception as e:
        return jsonify({"detail": f"Extraction failed: {e}"}), 400

    # 🔑 Score with your existing code and return the usual shape
    result = score_resume_core(
        resume_text=resume_text,
        job_text=job_text,
        job_title=job_title,
        is_pro=is_pro,
    )
    return jsonify(result), 200
