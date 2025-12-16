import re
from typing import List, Dict, Any

_METRIC_RE = re.compile(
    r"(\b\d+(\.\d+)?\s*%|\b\d+(\.\d+)?\s*(ms|sec|secs|seconds|mins|minutes|hrs|hours)\b|"
    r"\b\d+(\.\d+)?\s*(x|pp)\b|[$€£]\s*\d+|\b\d{1,3}\s*(k|m|b)\b|\b\d+\+\b)",
    re.IGNORECASE,
)

_ANY_DIGIT_RE = re.compile(r"\d")

def resume_has_metrics(resume_text: str) -> bool:
    if not resume_text:
        return False
    # If they have any numeric evidence at all, allow numeric suggestions.
    # (You can tighten this later to require %/$/time units only.)
    return bool(_ANY_DIGIT_RE.search(resume_text))

def strip_numbers(text: str) -> str:
    """
    Remove numeric claims to avoid invented metrics.
    Also removes trailing 'by ...' fragments.
    """
    if not text:
        return text

    # Remove common "by 30%" / "by 2x" phrases first
    text = re.sub(r"\bby\s+\d+(\.\d+)?\s*(%|x|pp)\b", "", text, flags=re.IGNORECASE)

    # Remove remaining metric-like tokens
    text = _METRIC_RE.sub("", text)

    # Remove any leftover standalone digits (e.g., "10+ APIs")
    text = re.sub(r"\b\d+\+?\b", "", text)

    # Cleanup whitespace/punctuation
    text = re.sub(r"\s{2,}", " ", text).strip()
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    return text

def hedge_if_needed(text: str) -> str:
    if not text:
        return text

    if re.search(r"\b(aimed to|helped|contributed to|worked to|supported|improved)\b", text, re.IGNORECASE):
        return text

    # Avoid "Helped improved ..." if the string starts with "Improved ..."
    if re.match(r"^\s*improv(ed|ing)\b", text, re.IGNORECASE):
        return f"Aimed to {text[0].lower() + text[1:]}" if len(text) > 1 else f"Aimed to {text}"

    return f"Helped {text[0].lower() + text[1:]}" if len(text) > 1 else f"Helped {text}"

def enforce_no_fake_metrics(suggestions: List[Dict[str, Any]], resume_text: str) -> List[Dict[str, Any]]:
    """
    If resume contains no digits, strip numeric claims from suggestions and hedge wording.
    """
    if resume_has_metrics(resume_text):
        return suggestions

    out: List[Dict[str, Any]] = []
    for s in suggestions or []:
        s2 = dict(s)
        st = s2.get("suggestedText") or ""

        if _ANY_DIGIT_RE.search(st) or _METRIC_RE.search(st):
            st2 = hedge_if_needed(strip_numbers(st))
            s2["suggestedText"] = st2
            if s2.get("reason"):
                s2["reason"] = f"{s2['reason']} (Avoided adding new numbers not present in resume.)"

        out.append(s2)
    return out