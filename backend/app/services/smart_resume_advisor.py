from dataclasses import dataclass
from typing import List, Dict, Tuple
import re

import numpy as np
from sentence_transformers import SentenceTransformer, util
from keybert import KeyBERT
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans


from app.utils.text_norm import normalize


_EMB = None
_KW = None

def get_emb():
    global _EMB
    if _EMB is None:
        print("Loading MiniLM embedder...")
        _EMB = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _EMB

def get_kw():
    global _KW
    if _KW is None:
        print("Loading KeyBERT...")
        _KW = KeyBERT(model="all-MiniLM-L6-v2")
    return _KW


CANON_SKILLS = [
    "python","java","c#","javascript","typescript","react","node.js","asp.net",
    "sql","postgresql","mysql","azure","aws","git","github actions","ci/cd",
    "docker","kubernetes","unit testing","integration testing","playwright",
    "jest","mocha","junit","agile","scrum","rest api","graphql","security",
    "oauth2","jwt","logging","monitoring","ml","nlp","ml.net","pandas",
    "scikit-learn","azure devops","terraform"
]
ACTION_VERBS_SET = set([
    "built","designed","implemented","optimized","migrated",
    "automated","led","owned","delivered","deployed",
    "scaled","mentored","improved","created","developed"
])
NON_TECH_GENERIC_VERBS = {
    "led","owned","mentored" 
}

_EXTRA_TECH_SYNS = {
    "react","reactjs","node","nodejs","sql","db","database","docker",
    "k8s","kubernetes","azure","aws","cloud","api","rest","graphql",
    "testing","unit","integration","ml","ai","nlp","devops","pipeline"
}

@dataclass
class SmartAdvice:
    fit_estimate: int
    sim_resume_jd: float
    present_skills: List[str]
    missing_skills: List[str]
    critical_gaps: List[str]
    section_suggestions: Dict[str, List[str]]
    ready_bullets: List[str]
    rewrite_hints: List[str]

def _embed(text: str):
    model = get_emb()  # ✅ FIX
    return model.encode([text], normalize_embeddings=True)



def _sim(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return float(util.cos_sim(_embed(a), _embed(b))[0][0])


def _keybert_terms(text: str, top_n=12) -> List[str]:
    kw = get_kw()  # ✅ FIX
    terms = []
    for term, _ in kw.extract_keywords(text, top_n=top_n, stop_words="english"):
        term = normalize(term)
        if len(term) >= 3 and term not in terms:
            terms.append(term)
    return terms

def _tfidf_terms(jd: str, resume: str, limit=150) -> List[str]:
    vec = TfidfVectorizer(
        ngram_range=(1,2),
        stop_words="english",
        max_features=600
    )
    X = vec.fit_transform([jd, resume])
    vocab = vec.get_feature_names_out().tolist()
    weights = X[0].toarray().ravel()
    order = np.argsort(-weights)
    return [vocab[i] for i in order if len(vocab[i]) >= 3][:limit]

NOISE_SUBSTRINGS = [
    # compliance / legal / HR boilerplate
    "country", "qualification", "qualifications", "citizenship", "right to work", "authorization",
    "sponsorship", "visa", "work permit", "background check", "drug", "eeo", "equal opportunity",
    "accommodation", "disability", "veteran", "race", "religion", "gender", "national origin",
    # non-skill logistics
    "salary", "pay range", "benefits", "compensation", "location", "remote", "hybrid", "on-site",
    # misc non-actionable
    "country qualifications", "must be able", "strong communication", "fast-paced", "self-starter"
]
KEYWORD_FAMILIES: Dict[str, List[str]] = {
    "edc_medidata_rave": [
        "medidata",
        "rave",
        "medidata rave",
        "rave edc",
    ],
    # Add other *specific* products only if you see repeated unsafe suggestions:
    # "edc_other": ["oracle siebel clinical", "inform", "veeva vault cdms", "redcap"],
}
_GENERIC_EVIDENCE_TOKENS = {
    # Tokens that are too generic to count as evidence for domain-specific claims
    "database", "databases", "system", "systems", "platform", "service", "services",
    "application", "applications", "api", "apis", "security", "secure", "compliance",
    "compliant", "standards", "industry", "requirements", "data", "information"
}
def _is_noisy_phrase(p: str) -> bool:
    p_l = p.lower().strip()
    if len(p_l) <= 2:
        return True

    for sub in NOISE_SUBSTRINGS:
        if sub in p_l:
            return True
        
    if len(p_l.split()) > 4 and not re.search(r"[0-9#\.+\-/]", p_l):
        return True
    return False

def _top_job_phrases(job_text: str, resume_text: str, top_k: int = 40) -> List[str]:
    """Job-only phrases via TF-IDF (1–3 grams) + KeyBERT ranking (with noise filtering)."""
    tfidf = TfidfVectorizer(
        ngram_range=(1,3),
        stop_words="english",
        max_features=1200,
        token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9\-\+\.#]+\b"
    )
    X = tfidf.fit_transform([job_text, resume_text])  
    vocab = np.array(tfidf.get_feature_names_out())
    job_w = X[0].toarray()[0]
    res_w = X[1].toarray()[0]
    score = job_w - res_w                      
    order = np.argsort(-score)
    tfidf_top = [vocab[i] for i in order if score[i] > 0][:top_k]

    kb = [t for t in _keybert_terms(job_text, top_n=top_k) if t not in tfidf_top]
    seen, out = set(), []
    for p in tfidf_top + kb:
        if len(p) >= 3 and p not in seen and not _is_noisy_phrase(p):
            out.append(p); seen.add(p)
    return out[:top_k]

def _sem_not_covered(phrases: List[str], resume_text: str, thr: float = 0.78) -> List[str]:
    if not phrases:
        return []
    model = get_emb()  # ✅ FIX
    res_vec = model.encode([resume_text], normalize_embeddings=True)[0]
    ph_vecs = model.encode(phrases, normalize_embeddings=True)
    res_n = np.linalg.norm(res_vec) + 1e-12
    keep = []
    for p, v in zip(phrases, ph_vecs):
        sim = float(np.dot(v, res_vec) / ((np.linalg.norm(v) + 1e-12) * res_n))
        if sim < thr:
            keep.append(p)
    return keep

def _cluster_themes(phrases: List[str], max_k: int = 4) -> Dict[str, List[str]]:
    if not phrases:
        return {}
    if len(phrases) <= 6:
        return {phrases[0]: phrases}
    model = get_emb()  # ✅ FIX
    V = model.encode(phrases, normalize_embeddings=True)
    k = min(max_k, max(2, len(phrases) // 6))
    km = KMeans(n_clusters=k, n_init="auto", random_state=42)
    labels = km.fit_predict(V)
    groups: Dict[str, List[str]] = {}
    for lab in range(k):
        idxs = np.where(labels == lab)[0]
        centroid = km.cluster_centers_[lab]
        rep_idx = min(idxs, key=lambda i: np.linalg.norm(V[i] - centroid))
        rep = phrases[rep_idx]
        groups[rep] = [phrases[i] for i in idxs]
    return groups

def _has_term(haystack_norm: str, term_norm: str) -> bool:
    if not haystack_norm or not term_norm:
        return False
    pat = r"(?<![a-z0-9])" + re.escape(term_norm) + r"(?![a-z0-9])"
    return re.search(pat, haystack_norm) is not None

def _resume_has_family(resume_text_norm: str, family_terms: List[str]) -> bool:
    if not resume_text_norm:
        return False
    for t in family_terms:
        t_n = normalize(t)
        if t_n and _has_term(resume_text_norm, t_n):
            return True
    return False

def _unsafe_family_for_phrase(phrase: str, resume_text_norm: str) -> bool:
    p = normalize(phrase or "")
    if not p:
        return False

    for _, terms in KEYWORD_FAMILIES.items():
        mentions_family = any(_has_term(p, normalize(t)) for t in terms if t)
        if mentions_family:
            return not _resume_has_family(resume_text_norm, terms)

    return False

def _expand_to_canon(terms: List[str]) -> List[str]:
    if not terms:
        return []
    model = get_emb()  # ✅ FIX
    e_can = model.encode(CANON_SKILLS, normalize_embeddings=True)
    e_terms = model.encode(terms, normalize_embeddings=True)
    sims = util.cos_sim(e_terms, e_can)
    picked = {CANON_SKILLS[int(sims[i].argmax())] for i in range(len(terms))}
    return sorted(picked)

def _extract_action_verbs(text: str):
    """
    Return action verbs appearing in sentences that contain tech terms.
    Filters out generic verbs without nearby tech context.
    """
    if not text:
        return []
    txt = text.lower()
    # Split into rough sentences
    sentences = re.split(r'[.\n\r;!?]+', txt)
    tech_vocab = set(CANON_SKILLS) | _EXTRA_TECH_SYNS
    picked = set()

    for sent in sentences:
        sent_l = sent.strip()
        if not sent_l:
            continue
        # Require at least one tech token in sentence
        if not any(t in sent_l for t in tech_vocab):
            continue
        words = re.findall(r'[a-zA-Z]+', sent_l)
        for w in words:
            if w in ACTION_VERBS_SET:
                picked.add(w)


    if picked:
        tokens = re.findall(r'[a-zA-Z]+', txt)
        positions = {i: tok for i, tok in enumerate(tokens)}
        tech_positions = {i for i, tok in positions.items() if tok in tech_vocab}
        refined = set()
        for i, tok in positions.items():
            if tok in picked:
                window = range(max(0, i-6), min(len(tokens), i+7))
                if tok in NON_TECH_GENERIC_VERBS and not any(j in tech_positions for j in window):
                    continue
                refined.add(tok)
        picked = refined

    return sorted(picked)


def _resume_mentions_phrase(resume_text_norm: str, phrase: str) -> bool:
    """
    Conservative check: if the resume doesn't literally mention the phrase (or close token),
    treat it as not-evidenced (avoid claiming experience).
    """
    if not resume_text_norm or not phrase:
        return False

    p = normalize(phrase)
    if not p:
        return False

    # Direct phrase match
    if _has_term(resume_text_norm, p):
        return True

    toks_all = [t for t in re.split(r"\s+", p) if t]
    toks = [
        t for t in toks_all
        if len(t) >= 4 and t not in _GENERIC_EVIDENCE_TOKENS
    ]

    if not toks:
        return False

    hits = sum(1 for t in toks if _has_term(resume_text_norm, t))

    # For multi-token concepts, require >=2 meaningful hits when possible
    if len(toks) >= 2:
        return hits >= 2

    return hits >= 1

def _should_soften_claim(phrase: str, resume_text_norm: str) -> bool:
    """
    True => do not generate/apply "experience" phrasing for this phrase.
    We soften if:
      - it belongs to a family not in resume (your existing rule), OR
      - it's not evidenced in the resume at all (general anti-hallucination rule).
    """
    if not phrase:
        return False
    if _unsafe_family_for_phrase(phrase, resume_text_norm):
        return True
    return not _resume_mentions_phrase(resume_text_norm, phrase)

def _compose_auto_suggestions(job_text: str, resume_text: str,
                              present_skills: List[str], missing_skills: List[str],
                              job_title: str) -> Tuple[Dict[str, List[str]], List[str]]:
    top = _top_job_phrases(job_text, resume_text, top_k=40)
    top = [p for p in top if not _is_noisy_phrase(p)]
    missing_phr = _sem_not_covered(top, resume_text, thr=0.78)
    themes = _cluster_themes(missing_phr, max_k=4)

    resume_norm = normalize(resume_text or "")

    exp: List[str] = []
    for rep, items in list(themes.items())[:4]:
        if _is_noisy_phrase(rep):
            continue
        exemplars = [w for w in items if w != rep][:2]

        # NEW: soften if not evidenced OR unsafe family
        unsafe = _should_soften_claim(rep, resume_norm) or any(
            _should_soften_claim(x, resume_norm) for x in exemplars
        )

        if unsafe:
            ex_txt = f" (e.g., {', '.join(exemplars)})" if exemplars else ""
            exp.append(
                f"If you haven’t actually used **{rep}**, don’t write it as experience. "
                f"Instead, phrase it as **learning/familiarity/interest**{ex_txt} (e.g., "
                f"“Currently learning {rep}”, “Familiar with concepts”, “Interested in working with {rep}”), "
                f"or add it under a **Training/Projects** section."
            )
        else:
            if exemplars:
                exp.append(
                    f"Add a results‑driven bullet illustrating **{rep}** (e.g., {', '.join(exemplars)}) and quantify impact."
                )
            else:
                exp.append(
                    f"Add a concise bullet demonstrating **{rep}** with a clear metric (%, ms, errors reduced) and the business/context outcome."
                )

    prj: List[str] = []
    top_keys = [k for k in list(themes.keys()) if not _is_noisy_phrase(k)][:3]

    # NEW: consider "not evidenced" as unsafe too
    any_unsafe_top = any(_should_soften_claim(k, resume_norm) for k in top_keys)

    if top_keys:
        if any_unsafe_top:
            prj.append(
                "For JD tools/terms not present in your resume, add an honest learning project/training entry to build credibility around: "
                + ", ".join(top_keys)
                + " (avoid implying production experience)."
            )
        else:
            prj.append(
                "Deliver a focused side project applying "
                + ", ".join(top_keys)
                + "; document architecture, automated tests, deployment steps, and 1–2 key metrics (e.g., response time, accuracy)."
            )

    strengths = present_skills[:2]
    mix_list = (top_keys + strengths)[:3]
    mix = ", ".join(mix_list) if mix_list else "core technologies for the role"
    title_txt = job_title or "the target role"
    summ = [
        f"Craft a professional 2–3 line summary tailored to **{title_txt}**, highlighting {mix} and a quantified accomplishment."
    ]

    bullets: List[str] = []
    if top_keys:
        first = top_keys[0]
        if _should_soften_claim(first, resume_norm):
            bullets.append(
                f"Currently learning / building familiarity with **{first}** through projects or coursework (avoid claiming hands‑on experience unless it’s true)."
            )
        else:
            bullets.append(
                f"Implemented {first} solution improving a key metric by Z% (define metric: latency, reliability, conversion) while ensuring maintainable code and test coverage."
            )

    bullets.append(
        "Structure each bullet: Action verb + Technology + Metric + Business/quality outcome (omit filler; keep to one sentence)."
    )

    return {"Summary": summ, "Experience": exp, "Projects": prj}, bullets

def smart_predict_resume_improvements(resume_text: str, job_text: str, job_title: str = "") -> SmartAdvice:
    r = normalize(resume_text); j = normalize(job_text); t = normalize(job_title or "")

    sim_rj = _sim(r, j)
    sim_rt = _sim(r, t) if t else 0.0

    jd_terms  = list(dict.fromkeys(_keybert_terms(j) + _tfidf_terms(j, r)))
    jd_skills = _expand_to_canon(jd_terms)

    present, missing = [], []
    for s in jd_skills:
        (present if s in r else missing).append(s)

    crit = [(s, max(_sim(s, j), _sim(s, t) if t else 0.0)) for s in missing]
    crit.sort(key=lambda x: -x[1])
    critical_gaps = [s for s, _ in crit[:6]]

    coverage = len(present) / max(1, (len(present) + len(missing)))
    fit = int(round(max(0, min(1.0, sim_rj*0.6 + sim_rt*0.2 + coverage*0.2)) * 100))

    section_suggestions, bullets = _compose_auto_suggestions(
        job_text=j,
        resume_text=r,
        present_skills=sorted(present),
        missing_skills=sorted(missing),
        job_title=job_title
    )

    verbs = _extract_action_verbs(r)
    rewrite_hints = ([
        "Start bullets with strong verbs (Built, Designed, Automated).",
        "Quantify impact (%, time saved, errors reduced, latency).",
        "Group tools into a single Skills section (Backend/Frontend/DevOps)."
    ] if len(verbs) < 3 else [
        "Keep bullets one sentence: Action → Tech → Result.",
        "Mirror the job’s nouns/verbs in Summary and top bullets.",
        "Move the most relevant project to the top."
    ])

    return SmartAdvice(
        fit_estimate=fit,
        sim_resume_jd=round(sim_rj, 4),
        present_skills=sorted(present)[:30],
        missing_skills=sorted(missing)[:30],
        critical_gaps=critical_gaps,
        section_suggestions=section_suggestions,
        ready_bullets=bullets[:6] or ["Add one bullet that proves measurable impact."],
        rewrite_hints=rewrite_hints
    )  
