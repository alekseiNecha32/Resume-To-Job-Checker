from dataclasses import dataclass
from typing import List, Dict

from sentence_transformers import SentenceTransformer, util
from keybert import KeyBERT
from sklearn.feature_extraction.text import TfidfVectorizer
import spacy

from app.utils.text_norm import normalize

# Load once
EMB = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
KW  = KeyBERT(model="all-MiniLM-L6-v2")
NLP = spacy.load("en_core_web_sm")

CANON_SKILLS = [
    "python","java","c#","javascript","typescript","react","node.js","asp.net",
    "sql","postgresql","mysql","azure","aws","git","github actions","ci/cd",
    "docker","kubernetes","unit testing","integration testing","playwright",
    "jest","mocha","junit","agile","scrum","rest api","graphql","security",
    "oauth2","jwt","logging","monitoring","ml","nlp","ml.net","pandas",
    "scikit-learn","azure devops","terraform"
]
ACTION_VERBS = ["built","designed","implemented","optimized","migrated",
               "automated","led","owned","delivered","deployed","scaled","mentored","improved"]

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
    return float(util.cos_sim(_embed(a), _embed(b))[0][0])

def _keybert_terms(text: str, top_n=12) -> List[str]:
    terms = []
    for term, _ in KW.extract_keywords(text, top_n=top_n, stop_words="english"):
        term = normalize(term)
        if len(term) >= 3 and term not in terms:
            terms.append(term)
    return terms

def _tfidf_terms(jd: str, resume: str, limit=150) -> List[str]:
    vec = TfidfVectorizer(ngram_range=(1,2), stop_words="english", max_features=600)
    X = vec.fit_transform([jd, resume])
    vocab = vec.get_feature_names_out().tolist()
    import numpy as np
    weights = X[0].toarray().ravel()
    order = np.argsort(-weights)
    return [vocab[i] for i in order if len(vocab[i]) >= 3][:limit]

def _expand_to_canon(terms: List[str]) -> List[str]:
    if not terms: return []
    e_can = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2").encode(
        CANON_SKILLS, normalize_embeddings=True
    )  # uses same model; already loaded above
    e_terms = EMB.encode(terms, normalize_embeddings=True)
    sims = util.cos_sim(e_terms, e_can)
    picked = {CANON_SKILLS[int(sims[i].argmax())] for i in range(len(terms))}
    return sorted(picked)

def _extract_action_verbs(text: str) -> List[str]:
    doc = NLP(text)
    verbs = {t.lemma_.lower() for t in doc if t.pos_ == "VERB" and t.lemma_.lower() in ACTION_VERBS}
    return sorted(list(verbs))

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

    section_suggestions = {"Summary": [], "Experience": [], "Projects": []}
    if t and sim_rt < 0.35:
        top = ", ".join((critical_gaps[:3] or missing[:3]))
        section_suggestions["Summary"].append(
            f"Add a 2–3 line summary aligned to “{job_title}” and highlight {top}."
        )
    if any(x in missing for x in ["ci/cd","github actions","azure devops"]):
        section_suggestions["Experience"].append("Add a CI/CD bullet: pipelines on PR, tests, auto-deploy (tool + impact).")
    if any(x in missing for x in ["unit testing","integration testing"]):
        section_suggestions["Experience"].append("Add testing results (framework + coverage % or defect reduction).")
    if any(x in missing for x in ["security","oauth2","jwt"]):
        section_suggestions["Experience"].append("Add security details (OAuth2/JWT, input validation, secrets).")

    bullets = []
    if "ci/cd" in critical_gaps or "github actions" in critical_gaps:
        bullets.append("Built CI/CD pipelines (GitHub Actions) running unit/E2E tests and deploying Docker images; cut release time by 40%.")
    if "unit testing" in critical_gaps:
        bullets.append("Implemented unit tests (Jest/JUnit) and E2E tests (Playwright); improved coverage 45%→85%, reduced regressions.")
    if "rest api" in critical_gaps:
        bullets.append("Designed REST APIs and added caching; lowered avg latency 320ms→140ms.")
    if any(x in critical_gaps for x in ["sql","postgresql","mysql"]):
        bullets.append("Optimized SQL with indexes & query tuning; sped up heavy report 9.2s→2.1s.")
    if any(x in critical_gaps for x in ["docker","kubernetes"]):
        bullets.append("Containerized services with Docker; per-branch review apps improved onboarding and parity.")

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
