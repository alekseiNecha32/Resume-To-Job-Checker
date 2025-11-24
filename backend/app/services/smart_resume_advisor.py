from dataclasses import dataclass
from typing import List, Dict, Tuple
import re

import numpy as np
from sentence_transformers import SentenceTransformer, util
from keybert import KeyBERT
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans


from app.utils.text_norm import normalize


EMB = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
KW = KeyBERT(model="all-MiniLM-L6-v2")


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
    return EMB.encode([text], normalize_embeddings=True)


def _sim(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return float(util.cos_sim(_embed(a), _embed(b))[0][0])


def _keybert_terms(text: str, top_n=12) -> List[str]:
    terms = []
    for term, _ in KW.extract_keywords(text, top_n=top_n, stop_words="english"):
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
    """Keep job phrases that the resume doesn't already cover semantically."""
    if not phrases:
        return []
    res_vec = EMB.encode([resume_text], normalize_embeddings=True)[0]
    ph_vecs = EMB.encode(phrases, normalize_embeddings=True)
    res_n = np.linalg.norm(res_vec) + 1e-12
    keep = []
    for p, v in zip(phrases, ph_vecs):
        sim = float(np.dot(v, res_vec) / ((np.linalg.norm(v) + 1e-12) * res_n))
        if sim < thr:
            keep.append(p)
    return keep

def _cluster_themes(phrases: List[str], max_k: int = 4) -> Dict[str, List[str]]:
    """Cluster remaining phrases (MiniLM) into themes to drive suggestions."""
    if not phrases:
        return {}
    if len(phrases) <= 6:
        return {phrases[0]: phrases}
    V = EMB.encode(phrases, normalize_embeddings=True)
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


def _expand_to_canon(terms: List[str]) -> List[str]:
    if not terms:
        return []
    e_can = EMB.encode(CANON_SKILLS, normalize_embeddings=True)
    e_terms = EMB.encode(terms, normalize_embeddings=True)
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


def _compose_auto_suggestions(job_text: str, resume_text: str,
                              present_skills: List[str], missing_skills: List[str],
                              job_title: str) -> Tuple[Dict[str, List[str]], List[str]]:
    top = _top_job_phrases(job_text, resume_text, top_k=40)
    top = [p for p in top if not _is_noisy_phrase(p)]
    missing_phr = _sem_not_covered(top, resume_text, thr=0.78)
    themes = _cluster_themes(missing_phr, max_k=4)

    exp: List[str] = []
    for rep, items in list(themes.items())[:4]:
        if _is_noisy_phrase(rep):
            continue
        exemplars = [w for w in items if w != rep][:2]
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
    if top_keys:
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
        f"Craft a professional 2–3 line summary tailored to **{title_txt}**, highlighting {mix} and a quantified accomplishment (e.g., reduced build time 30%, improved model accuracy 12pp)."
    ]

    bullets: List[str] = []
    if top_keys:
        bullets.append(
            f"Implemented {top_keys[0]} solution improving a key metric by Z% (define metric: latency, reliability, conversion) while ensuring maintainable code and test coverage."
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
