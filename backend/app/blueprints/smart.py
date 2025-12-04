from flask import Blueprint, current_app, request, jsonify
from app.services.smart_resume_advisor import smart_predict_resume_improvements
from supabase import create_client
import os
from dotenv import load_dotenv
import logging
from openai import OpenAI

smart_bp = Blueprint("smart", __name__, url_prefix="/api/smart")
logger = logging.getLogger(__name__)

def get_user_id():
    return request.headers.get("X-User-Id")

@smart_bp.route("/analyze", methods=["POST", "OPTIONS"])
def analyze():
    if request.method == "OPTIONS":
        return ("", 204)
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
        if not d or not d.get("resume_text") or not d.get("job_text"):
            return jsonify({"error": "Missing resume_text or job_text"}), 400

        print(f"Starting smart analysis for user {uid}...")
        res = smart_predict_resume_improvements(
            resume_text=d.get("resume_text", ""),
            job_text=d.get("job_text", ""),
            job_title=d.get("job_title", "")
        )
       
        suggestions_text = None
        client = current_app.config.get("OPENAI_CLIENT")
        
        if client and res:
                    prompt = f"""
        You are an ATS expert. Produce concise, actionable “Personal Suggestions” focused ONLY on hard technical skills,
        tools, frameworks, and specific deliverables that strengthen the resume for this job. Ignore soft skills like
        communication, leadership, cross time zone collaboration, culture fit.

        Return 4–6 short bullet points.

        Job Title: {d.get("job_title","")}

        Missing/underrepresented hard skills:
        {", ".join(res.missing_skills or [])}

        Resume (excerpt):
        {(d.get("resume_text","") or "")[:2000]}

        Job description (excerpt):
        {(d.get("job_text","") or "")[:2000]}
        """.strip()
                    try:
                        completion = client.responses.create(model="gpt-4.1-mini", input=prompt)
                        suggestions_text = completion.output_text
                    except Exception as e:
                        logger.warning(f"OpenAI suggestions failed: {e}")
                        suggestions_text = None

        if res is None:
            return jsonify({"error": "Analysis failed - returned None"}), 500

        # Deduct credits
        try:
            supabase.table("profiles").update({"credits": credits - 1}).eq("user_id", uid).execute()
        except Exception as e:
            logger.error(f"Failed to deduct credits: {e}")
            pass

        # Save to DB (include personal_suggestions)
        try:
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
                    "personal_suggestions": suggestions_text,  # NEW
                },
                "resume_excerpt": d.get("resume_text", "")[:300]
            }).execute()
        except Exception as e:
            logger.error(f"Failed to save analysis: {e}")

        logger.info(f"smart_analyze uid={uid} fit={res.fit_estimate} missing={len(res.missing_skills or [])}")

        return jsonify({
            "fit_estimate": res.fit_estimate,
            "similarity_resume_job": res.sim_resume_jd,
            "present_skills": res.present_skills,
            "missing_skills": res.missing_skills,
            "critical_gaps": res.critical_gaps,
            "section_suggestions": res.section_suggestions,
            "ready_bullets": res.ready_bullets,
            "rewrite_hints": res.rewrite_hints,
            "personal_suggestions": suggestions_text,  # NEW
            "remaining_credits": credits - 1,
            "model_source": {
                "scoring": "MiniLM",
                "suggestions": "gpt-4.1-mini" if suggestions_text else None
            }
        }), 200

    except Exception as e:
        logger.error(f"smart_analyze error: {e}", exc_info=True)
        return jsonify({"error": str(e), "type": type(e).__name__}), 500     
                    
    #     if res is None:
    #         return jsonify({"error": "Analysis failed - returned None"}), 500

    #     # Deduct credits
    #     try:
    #         supabase.table("profiles").update({"credits": credits - 1}).eq("user_id", uid).execute()
    #     except Exception as e:
    #         logger.error(f"Failed to deduct credits: {e}")
    #         # Don't fail - user already got analysis
    #         pass

    #     # Save to DB
    #     try:
    #         supabase.table("analyses").insert({
    #             "user_id": uid,
    #             "job_title": d.get("job_title", ""),
    #             "fit_estimate": res.fit_estimate,
    #             "payload": {
    #                 "fit_estimate": res.fit_estimate,
    #                 "similarity_resume_job": res.sim_resume_jd,
    #                 "present_skills": res.present_skills,
    #                 "missing_skills": res.missing_skills,
    #                 "critical_gaps": res.critical_gaps,
    #                 "section_suggestions": res.section_suggestions,
    #                 "ready_bullets": res.ready_bullets,
    #                 "rewrite_hints": res.rewrite_hints,
    #             },
    #             "resume_excerpt": d.get("resume_text", "")[:300]
    #         }).execute()
    #     except Exception as e:
    #         logger.error(f"Failed to save analysis: {e}")
    #         # Don't fail - analysis is done

    #     logger.info(f"smart_analyze uid={uid} fit={res.fit_estimate} missing={len(res.missing_skills)}")

    #     return jsonify({
    #         "fit_estimate": res.fit_estimate,
    #         "similarity_resume_job": res.sim_resume_jd,
    #         "present_skills": res.present_skills,
    #         "missing_skills": res.missing_skills,
    #         "critical_gaps": res.critical_gaps,
    #         "section_suggestions": res.section_suggestions,
    #         "ready_bullets": res.ready_bullets,
    #         "rewrite_hints": res.rewrite_hints,
    #         "remaining_credits": credits - 1
    #     }), 200

    # except Exception as e:
    #     logger.error(f"smart_analyze error: {e}", exc_info=True)
    #     return jsonify({"error": str(e), "type": type(e).__name__}), 500                
       