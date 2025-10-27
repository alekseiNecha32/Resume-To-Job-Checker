import re

def normalize(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"[^a-z0-9+#/.\-\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t
