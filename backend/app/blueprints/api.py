import os
from flask import Blueprint, request, jsonify
from werkzeug.exceptions import BadRequest
from app.utils.extractors import extract_any, sniff_ext

from sentence_transformers import SentenceTransformer, util
import os
import logging
logger = logging.getLogger(__name__)
# Global model cache - load only once
_SBERT = None

def get_sbert_model():
    """Lazy load SentenceTransformer to avoid memory issues"""
    global _SBERT
    if _SBERT is None:
        print("🔄 Loading SentenceTransformer model (first request)...")
        try:
            _SBERT = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            # Warmup
            _ = _SBERT.encode("warmup", convert_to_tensor=True, normalize_embeddings=True)
            print("✅ Model loaded successfully")
        except Exception as e:
            print(f"❌ Failed to load model: {e}")
            _SBERT = None
            raise
    return _SBERT

api_bp = Blueprint("api", __name__, url_prefix="/api")

@api_bp.get("/ping")
def ping():
    return jsonify({"message": "pong"}), 200

MAX_SIZE = 5 * 1024 * 1024  

STOPWORDS = {
    "a","an","the","and","or","to","of","in","on","for","with","at","by","from",
    "is","are","was","were","be","as","that","this","it","its","your","you","we",
    "our","their","they","he","she","i", "good", "understanding", "knowledge", "strong", "excellent",
    "skills","technology","experience","knowledge","ability","strong","excellent"
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
    # Handle CORS preflight
    if request.method == "OPTIONS":
        return ("", 204)

    data = request.get_json(silent=True) or {}

    # Accept both camelCase and snake_case
    resume_text = _as_text(data.get("resumeText") or data.get("resume_text")).strip()
    job_text    = _as_text(data.get("jobText")    or data.get("job_text")).strip()
    job_title   = _as_text(data.get("jobTitle")   or data.get("job_title")).strip()

    if not resume_text or not job_text:
        return jsonify({"error": "Missing fields: resumeText, jobText"}), 400

    MAX_CHARS = 20000
    if len(resume_text) > MAX_CHARS:
        resume_text = resume_text[:MAX_CHARS]
    if len(job_text) > MAX_CHARS:
        job_text = job_text[:MAX_CHARS]
    import re
    from collections import Counter
    WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+#/-]*")

    TITLE_STOP = {
        "senior","sr","jr","junior","mid","level","ii","iii","iv",
        "remote","hybrid","onsite","contract","full","time","ft","pt",
        "position","role","about","opportunity","team","members","mentors",
        "start","least","between","including","etc","e.g","eg","ie","because",
        "nice","to","have","highly","preferred","required","years","experience",
        "2025","2026"
    }

    SKILL_HINTS = {
        "javascript","typescript","python","java","kotlin","c#","csharp","go","rust","sql","bash",
        "react","reactjs","angular","vue","svelte","nextjs","node","node.js","express","django","flask",
        "asp.net","aspnet",".net","spring","springboot","shadcn","tailwind",
        "playwright","jest","mocha","chai","junit","pytest","selenium","unit","integration","e2e","end-to-end","testing",
        "postgres","postgresql","mysql","mssql","sqlite","mongodb","redis",
        "docker","kubernetes","ci","cd","ci/cd","github","github actions","gitlab","azure","aws","gcp",
        "rest","api","graphql","grpc","socket","websocket",
        "oauth","jwt","openid","performance","accessibility","a11y","security"
    }

    def tokenize(s: str):
        return [t.lower() for t in WORD_RE.findall(s or "")]

    def is_noise(tok: str) -> bool:
        if tok in STOPWORDS:
            return True
        if tok in TITLE_STOP:
            return True
        if tok.isnumeric():
            return True
        if len(tok) <= 2 and tok not in {"c#","go","r","ui","ux"}:
            return True
        return False

    def bigrams(tokens):
        for i in range(len(tokens) - 1):
            a, b = tokens[i], tokens[i+1]
            if not is_noise(a) and not is_noise(b):
                yield f"{a} {b}"

    # ---- build keyword list from JD ----
    job_tokens_raw = tokenize(job_text)
    job_tokens = [t for t in job_tokens_raw if not is_noise(t)]

    if not job_tokens:
        return jsonify({"error": "No useful tokens in job description"}), 400

    freq = Counter(job_tokens)

    # boost any token that is in SKILL_HINTS
    for t in list(freq.keys()):
        if t in SKILL_HINTS:
            freq[t] += 2.5

    # boost job title tokens
    title_tokens = [t for t in tokenize(job_title) if not is_noise(t)]
    for t in title_tokens:
        freq[t] += 3.0

    bi = Counter(bigrams(job_tokens))
    for bg, cnt in bi.items():
        a, b = bg.split()
        bonus = 0.0
        if a in SKILL_HINTS or b in SKILL_HINTS:
            bonus += 0.8
        if re.search(r"[.+#/-]", a) or re.search(r"[.+#/-]", b):
            bonus += 0.8
        bi[bg] = cnt + bonus

    MAX_UNI = 16
    MAX_BI  = 8

    top_uni = [w for w, _ in freq.most_common(MAX_UNI)]
    top_bi  = [p for p, _ in bi.most_common(MAX_BI)]

    ordered = []
    seen = set()

    title_phrase = job_title.lower().strip()
    if title_phrase and len(title_tokens) >= 2:
        ordered.append(title_phrase)
        seen.add(title_phrase)

    for p in top_bi:
        if p not in seen:
            ordered.append(p)
            seen.add(p)

    for w in top_uni:
        if w not in seen:
            ordered.append(w)
            seen.add(w)

    job_keywords = ordered

    # ---- check what the resume actually covers ----
    resume_tokens = set(tokenize(resume_text))

    
   
    def literal_hit(term: str, text: str) -> bool:
        pattern = re.escape(term.lower()).replace(r"\ ", r"\s+")
        return re.search(pattern, text.lower()) is not None

    matched, missing = [], []
    for kw in job_keywords:
        if " " in kw:          # bigram / phrase
            hit = literal_hit(kw, resume_text)
        else:                  # unigram
            hit = kw in resume_tokens
        (matched if hit else missing).append(kw)

    total = len(job_keywords)
    coverage = (len(matched) / total) if total else 0.0
    score = int(round(coverage * 100))

    similarity = round(coverage, 4)

    return jsonify({
        "model": "simple-keyword-v1",
        "similarity": similarity,
        "score": score,
        "matchedKeywords": matched,
        "missingKeywords": missing,
        "jobKeywords": job_keywords,
        "coverage": round(coverage * 100),
        "totalKeywords": total,
        "matches": matched,
        "missing_keywords": missing,
        "denominator": total,
    }), 200

