import numpy as np
from app.utils.embeddings import get_embedder

def get_model():
    # keep same function name so the rest of the file doesn't change
    return get_embedder()




def chunk_text(text: str, max_chars: int = 1000):
    """Split text into chunks to avoid model input length limits."""
    text = (text or "").strip()
    if not text:
        return []
    chunks, start = [], 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            ws = text.rfind(" ", start, end)
            if ws != -1 and ws > start + 200:
                end = ws
        chunks.append(text[start:end].strip())
        start = end
    return chunks

def embed_text(text: str) -> np.ndarray:
    """Embed possibly long text safely."""
    try:
        model = get_model()
        chunks = chunk_text(text)
        if not chunks:
            return np.zeros((model.get_sentence_embedding_dimension(),), dtype=np.float32)
        embeddings = model.encode(chunks, normalize_embeddings=True)
        return np.mean(embeddings, axis=0)
    except Exception as e:
        print(f"[text_utils] Embedding failed: {e}")
        return np.zeros((384,), dtype=np.float32)

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a_norm = a / (np.linalg.norm(a) + 1e-12)
    b_norm = b / (np.linalg.norm(b) + 1e-12)
    return (float(np.dot(a_norm, b_norm)) + 1.0) / 2.0

def get_text_similarity(resume_text: str, job_text: str) -> float:
    resume_vec = embed_text(resume_text)
    job_vec = embed_text(job_text)
    return cosine_similarity(resume_vec, job_vec)
