from flask import Blueprint, request, jsonify
from app.services.smart_resume_advisor import smart_predict_resume_improvements

smart_bp = Blueprint("smart", __name__, url_prefix="/api/smart")

@smart_bp.post("/analyze")
def analyze():
    d = request.get_json(force=True)
    res = smart_predict_resume_improvements(
        resume_text=d.get("resume_text", ""),
        job_text=d.get("job_text", ""),
        job_title=d.get("job_title", "")
    )
    return jsonify({
        "fit_estimate": res.fit_estimate,
        "similarity_resume_job": res.sim_resume_jd,
        "present_skills": res.present_skills,
        "missing_skills": res.missing_skills,
        "critical_gaps": res.critical_gaps,
        "section_suggestions": res.section_suggestions,
        "ready_bullets": res.ready_bullets,
        "rewrite_hints": res.rewrite_hints
    }), 200
