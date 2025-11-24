from flask import Blueprint, request, jsonify
from app.services.smart_resume_advisor import smart_predict_resume_improvements
from supabase import create_client
import os
from dotenv import load_dotenv

smart_bp = Blueprint("smart", __name__, url_prefix="/api/smart")

def get_user_id():
    """Temporary dev helper — replace with JWT decoding later."""
    return request.headers.get("X-User-Id") 


# ...existing code...
@smart_bp.post("/analyze")
def analyze():
    try:
        load_dotenv()
        SUPABASE_URL = os.getenv("SUPABASE_URL")
        SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        print("DEBUG /smart/analyze: SUPABASE_URL set:", bool(SUPABASE_URL), "SUPABASE_KEY set:", bool(SUPABASE_KEY))

        if not SUPABASE_URL or not SUPABASE_KEY:
            return jsonify({"error": "server_misconfigured"}), 500

        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

        # Debug incoming headers
        headers = dict(request.headers)
        print("DEBUG /smart/analyze incoming headers:", headers)

        # 1) Dev override via X-User-Id
        uid = request.headers.get("X-User-Id")
        if uid:
            print("DEBUG /smart/analyze using X-User-Id:", uid)
        else:
            # 2) Try Authorization: Bearer <token>
            auth = request.headers.get("Authorization", "") or ""
            if not auth.lower().startswith("bearer "):
                print("DEBUG /smart/analyze no Bearer token and no X-User-Id")
                return jsonify({"error": "Unauthorized"}), 401
            token = auth.split(" ", 1)[1].strip()
            print("DEBUG /smart/analyze token prefix:", token[:40])

            user = None
            try:
                if hasattr(supabase.auth, "api") and hasattr(supabase.auth.api, "get_user"):
                    print("DEBUG /smart/analyze calling supabase.auth.api.get_user")
                    uresp = supabase.auth.api.get_user(token)
                    print("DEBUG /smart/analyze auth.api.get_user raw ->", repr(uresp))
                    user = (uresp.get("data") or {}).get("user") if isinstance(uresp, dict) else getattr(uresp, "user", None)
                elif hasattr(supabase.auth, "get_user"):
                    print("DEBUG /smart/analyze calling supabase.auth.get_user")
                    uresp2 = supabase.auth.get_user(token)
                    print("DEBUG /smart/analyze auth.get_user raw ->", repr(uresp2))
                    user = (uresp2.get("data") or {}).get("user") if isinstance(uresp2, dict) else getattr(uresp2, "user", None)
            except Exception as e:
                print("DEBUG /smart/analyze get_user exception:", repr(e))
                user = None

            if not user:
                print("DEBUG /smart/analyze user not resolved from token")
                return jsonify({"error": "Unauthorized"}), 401

            # extract uid for dict or object shapes
            uid = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
            print("DEBUG /smart/analyze resolved uid from token:", uid)
            if not uid:
                return jsonify({"error": "Unauthorized"}), 401

        # fetch profile safely (handle missing row)
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

    except Exception:
        import traceback
        print("UNCAUGHT /smart/analyze exception:")
        traceback.print_exc()
        return jsonify({"error": "internal_server_error"}), 500



# connect to Supabase
# SUPABASE_URL = os.environ["SUPABASE_URL"]
# SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
# supabase = create_client(SUPABASE_URL, SUPABASE_KEY)