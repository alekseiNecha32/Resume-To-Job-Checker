import os
from sentence_transformers import SentenceTransformer

_EMB = None

def get_embedder():
    global _EMB
    if _EMB is None:
        model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        _EMB = SentenceTransformer(model_name)
        _EMB.encode("warmup", convert_to_tensor=True, normalize_embeddings=True)
    return _EMB
