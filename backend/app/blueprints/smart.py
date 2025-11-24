from flask import Blueprint, request, jsonify
from app.services.smart_resume_advisor import smart_predict_resume_improvements
from supabase import create_client
import os
from dotenv import load_dotenv
import logging

smart_bp = Blueprint("smart", __name__, url_prefix="/api/smart")
logger = logging.getLogger(__name__)

def get_user_id():
    return request.headers.get("X-User-Id")

@smart_bp.post("/analyze")
def analyze():
    try:
        load_dotenv()
        SUPABASE_URL = os.getenv("SUPABASE_URL")
        SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not SUPABASE_URL or not SUPABASE_KEY:
            return jsonify({"error": "server_misconfigured"}), 500

        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

        uid = request.headers.get("X-User-Id")
        if not uid:
            auth = request.headers.get("Authorization", "") or ""
            if not auth.lower().startswith("bearer "):
                return jsonify({"error": "Unauthorized"}), 401
            token = auth.split(" ", 1)[1].strip()
            user = None
            try:
                if hasattr(supabase.auth, "api") and hasattr(supabase.auth.api, "get_user"):
                    uresp = supabase.auth.api.get_user(token)
                    user = (uresp.get("data") or {}).get("user") if isinstance(uresp, dict) else getattr(uresp, "user", None)
                elif hasattr(supabase.auth, "get_user"):
                    uresp2 = supabase.auth.get_user(token)
                    user = (uresp2.get("data") or {}).get("user") if isinstance(uresp2, dict) else getattr(uresp2, "user", None)
            except Exception:
                user = None
            if not user:
                return jsonify({"error": "Unauthorized"}), 401
            uid = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
            if not uid:
                return jsonify({"error": "Unauthorized"}), 401

        profile_res = supabase.table("profiles").select("credits").eq("user_id", uid).execute()
        pdata_raw = profile_res.get("data") if isinstance(profile_res, dict) else getattr(profile_res, "data", None)
        if isinstance(pdata_raw, list):
            pdata = pdata_raw[0] if pdata_raw else {}
        elif isinstance(pdata_raw, dict):
            pdata = pdata_raw
        else:
            pdata = {}
        credits = pdata.get("credits", 0)

        if credits <= 0:
            return jsonify({"error": "no_credits", "message": "Please purchase credits to use Smart Analysis."}), 402

        d = request.get_json(force=True)
        res = smart_predict_resume_improvements(
            resume_text=d.get("resume_text", ""),
            job_text=d.get("job_text", ""),
            job_title=d.get("job_title", "")
        )

        supabase.table("profiles").update({"credits": credits - 1}).eq("user_id", uid).execute()

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

        logger.info("smart_analyze uid=%s credits_before=%d fit=%.2f missing=%d",
                    uid, credits, res.fit_estimate, len(res.missing_skills))

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

    except Exception as e:
        logger.error("smart_analyze error=%s", e, exc_info=True)
        return jsonify({"error": "internal_server_error"}), 500