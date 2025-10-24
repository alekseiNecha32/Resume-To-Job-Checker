from __future__ import annotations
import re
from collections import defaultdict
from typing import Dict, List, Set, Tuple
from .text_utils import canon, norm_tokens, ngrams

TECH_PAT = re.compile(
    r"(?:[A-Za-z]\w*(?:[-./]\w+)+)|(?:[A-Z][a-z]+(?:\s[A-Z][a-z]+)*)|(?:[A-Za-z]+\d+)|(?:[A-Z]{2,})"
)

COMMON_IGNORE = {
    "team", "work", "working", "world", "academic", "university", "students", "staff",
    "being", "https", "all", "also", "after", "about", "every", "more", "anywhere", "offer"
}

def jd_candidates(job_text: str) -> Set[str]:
    cand = {canon(m.group(0)) for m in TECH_PAT.finditer(job_text)}
    toks = norm_tokens(job_text)
    for n in (1, 2, 3):
        for g in ngrams(toks, n):
            if len(g) >= 3:
                cand.add(g)
    # remove common junk terms
    return {c for c in cand if c not in COMMON_IGNORE and len(c) > 2}

def resume_candidates(resume_text: str) -> Set[str]:
    cand = {canon(m.group(0)) for m in TECH_PAT.finditer(resume_text)}
    toks = norm_tokens(resume_text)
    for n in (1, 2, 3):
        for g in ngrams(toks, n):
            if len(g) >= 3:
                cand.add(g)
    return cand

def score_dynamic(resume_text: str, job_text: str) -> Tuple[int, List[str], List[str], int]:
    jd_terms = sorted(jd_candidates(job_text))
    res_terms = sorted(resume_candidates(resume_text))
    if not jd_terms:
        return 0, [], [], 0

    matched = sorted(set(jd_terms) & set(res_terms))
    missing = sorted(set(jd_terms) - set(res_terms))
    score = round(100 * len(matched) / len(jd_terms))
    return score, matched, missing, len(jd_terms)
