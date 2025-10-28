from flask import Blueprint, request, jsonify
from app.services.smart_resume_advisor import smart_predict_resume_improvements
from supabase import create_client
import os
from dotenv import load_dotenv

smart_bp = Blueprint("smart", __name__, url_prefix="/api/smart")


# connect to Supabase
# SUPABASE_URL = os.environ["SUPABASE_URL"]
# SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
# supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_user_id():
    """Temporary dev helper — replace with JWT decoding later."""
    return request.headers.get("X-User-Id") 


@smart_bp.post("/analyze")
def analyze():
    
    load_dotenv()  
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    uid = get_user_id()
    if not uid:
        return jsonify({"error": "Unauthorized"}), 401

    # check user credits
    profile = supabase.table("profiles").select("credits").eq("user_id", uid).single().execute()
    profile_data = profile.data
    credits = profile_data["credits"] if profile_data else 0

    if credits <= 0:
        return jsonify({"error": "no_credits", "message": "Please purchase credits to use Smart Analysis."}), 402

    # parse request
    d = request.get_json(force=True)
    res = smart_predict_resume_improvements(
        resume_text=d.get("resume_text", ""),
        job_text=d.get("job_text", ""),
        job_title=d.get("job_title", "")
    )

    # deduct 1 credit
    supabase.table("profiles").update({"credits": credits - 1}).eq("user_id", uid).execute()

    # store analysis in DB
    supabase.table("analyses").insert({
        "user_id": uid,
        "job_title": d.get("job_title", ""),
        "fit_estimate": res.fit_estimate,
        "payload": {
            "fit_estimate": res.fit_estimate,
            "similarity_resume_job": res.sim_resume_jd,
            "present_skills": res.present_skills,
            "missing_skills": res.missing_skills,
            "critical_gaps": res.critical_gaps,
            "section_suggestions": res.section_suggestions,
            "ready_bullets": res.ready_bullets,
            "rewrite_hints": res.rewrite_hints,
        },
        "resume_excerpt": d.get("resume_text", "")[:300]
    }).execute()

    return jsonify({
        "fit_estimate": res.fit_estimate,
        "similarity_resume_job": res.sim_resume_jd,
        "present_skills": res.present_skills,
        "missing_skills": res.missing_skills,
        "critical_gaps": res.critical_gaps,
        "section_suggestions": res.section_suggestions,
        "ready_bullets": res.ready_bullets,
        "rewrite_hints": res.rewrite_hints,
        "remaining_credits": credits - 1
    }), 200