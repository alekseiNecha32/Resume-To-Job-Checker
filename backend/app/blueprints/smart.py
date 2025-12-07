from flask import Blueprint, current_app, request, jsonify
from app.services.smart_resume_advisor import smart_predict_resume_improvements
from supabase import create_client
import os
from dotenv import load_dotenv
import logging
import json
from uuid import uuid4 
smart_bp = Blueprint("smart", __name__, url_prefix="/api/smart")
logger = logging.getLogger(__name__)

def get_user_id():
    return request.headers.get("X-User-Id")


 # add this near other imports
# ...existing code...

@smart_bp.post("/suggest")
def suggest():
    body = request.get_json(force=True) or {}
    resume = body.get("resume") or {}
    job_text = (body.get("jobText") or "")[:4000]

    def fallback():
        sections = resume.get("sections") or []
        first_sec = sections[0] if sections else {}
        first_item = (first_sec.get("items") or [None])[0]
        return [
            {
                "id": f"add-{uuid4()}",
                "type": "add_bullet",
                "targetSectionId": first_sec.get("id", "experience"),
                "suggestedText": "Delivered KPI automation cutting reporting cycle time by 30%.",
                "reason": "Aligns to impact and metrics."
            },
            {
                "id": f"rewrite-{uuid4()}",
                "type": "rewrite_bullet",
                "targetSectionId": first_sec.get("id", "experience"),
                "targetItemId": first_item.get("id") if first_item else "item-1",
                "originalText": first_item.get("text") if first_item else "",
                "suggestedText": "Improved reliability by 25% via on-call playbooks and alert tuning.",
                "reason": "Emphasize measurable outcomes."
            },
            {
                "id": f"proj-{uuid4()}",
                "type": "project_idea",
                "targetSectionId": "projects",
                "suggestedText": "Built role-based dashboard reducing manual status pings by 80%.",
                "reason": "Shows relevant ownership and delivery."
            },
        ]

    client = current_app.config.get("OPENAI_CLIENT")
    if not client:
        return jsonify({"suggestions": fallback()})

    prompt = f"""
You generate resume edit suggestions.
Resume JSON: {resume}
Job: {job_text}
Return JSON array of 3 suggestions.
Each object:
- id: string
- type: add_bullet | rewrite_bullet | project_idea
- targetSectionId: existing section id or "projects"
- targetItemId: only for rewrite_bullet
- originalText: for rewrite_bullet
- suggestedText: concise, metric-focused
- reason: short reason
JSON only.
"""
    try:
        completion = client.responses.create(
            model="gpt-4.1-mini",
            input=[{"role": "user", "content": prompt}],
            max_output_tokens=800,
        )
        raw = completion.output[0].content[0].text
        suggestions = json.loads(raw)
    except Exception as e:
        logger.warning("suggest fallback: %s", e)
        suggestions = fallback()

    return jsonify({"suggestions": suggestions})


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

          # define inputs once
        resume_text = d.get("resume_text", "")
        job_text = d.get("job_text", "")
        job_title = d.get("job_title", "")

        print(f"Starting smart analysis for user {uid}...")
        res = smart_predict_resume_improvements(
            resume_text=resume_text,
            job_text=job_text,
            job_title=job_title
        )
       
        if res is None:
            return jsonify({"error": "Analysis failed - returned None"}), 500

        # Normalize for safety
        present_skills = res.present_skills or []
        missing_skills = res.missing_skills or []
        critical_gaps = res.critical_gaps or []
        section_suggestions = res.section_suggestions or {}
        ready_bullets = res.ready_bullets or []
        rewrite_hints = res.rewrite_hints or []

        suggestions_text = None
        lego_resume = None       # === LEGO BLOCKS ===
        lego_suggestions = None  # === LEGO BLOCKS ===
        client = current_app.config.get("OPENAI_CLIENT")
        
        if client and res:
                    # === LEGO BLOCKS: new JSON-based prompt for “Lego” UI ===
            prompt = f"""
You are an ATS expert and resume editor.

Your job is to analyze the resume and job description and propose improvements focused ONLY on hard technical skills, tools, frameworks, and concrete deliverables.

IMPORTANT RULES:
- Focus on things like programming languages, frameworks, libraries, tools, cloud, testing, automation, CI/CD, data/ML.
- IGNORE soft skills like communication, teamwork, cross time zone collaboration, leadership, culture fit, etc.
- Do not suggest generic “team player”, “strong communication”, “fast learner”, etc.

Context:
Job Title: {job_title}

Missing/underrepresented hard skills (from a MiniLM/KeyBERT engine):
{", ".join(missing_skills)}

Present hard skills:
{", ".join(present_skills)}

Critical gaps:
{", ".join(critical_gaps)}

Resume (raw text):
\"\"\"{resume_text[:3500]}\"\"\"

Job description (raw text):
\"\"\"{job_text[:3500]}\"\"\"

Return a SINGLE JSON object with this structure:

{{
  "personalSuggestionsText": "string with 4-6 short bullet points in markdown style, each starting with '- ' and all about hard technical improvements",

  "structuredResume": {{
    "sections": [
      {{
        "id": "experience",
        "title": "Experience",
        "items": [
          {{
            "id": "exp-1",
            "type": "bullet",
            "text": "Built X using Y resulting in Z."
          }}
        ]
      }}
      // Include other sections like "skills", "projects", "education" if they exist.
    ]
  }},

  "suggestions": [
    {{
      "id": "s1",
      "type": "add_bullet",  // one of: "add_bullet", "rewrite_bullet", "project_idea"
      "targetSectionId": "experience",  // e.g. "experience", "skills", "projects"
      "targetItemId": null,            // for add_bullet or project_idea this can be null/omitted
      "title": "Add impact-focused React testing bullet",
      "originalText": null,            // ONLY used for type="rewrite_bullet"
      "suggestedText": "Improved Playwright end-to-end coverage from 60% to 90% for admin flows, reducing regressions by 30%.",
      "reason": "Adds a quantified impact for your testing work."
    }},
    {{
      "id": "s2",
      "type": "rewrite_bullet",
      "targetSectionId": "experience",
      "targetItemId": "exp-1",        // must reference an item id from structuredResume.sections[].items[].id
      "title": "Rewrite for clarity and impact",
      "originalText": "Developed React components for internal dashboard.",
      "suggestedText": "Built reusable React components for an internal dashboard used by 3+ teams, reducing UI bugs by 25%.",
      "reason": "Shows scale of usage and measurable benefit."
    }},
    {{
      "id": "s3",
      "type": "project_idea",
      "targetSectionId": "projects",
      "targetItemId": null,
      "title": "Accessibility map mini project",
      "originalText": null,
      "suggestedText": "Accessibility Map – Built a web app that lets wheelchair users rate campus building accessibility using React, .NET, and map APIs.",
      "reason": "Demonstrates accessibility passion and your full-stack skills."
    }}
  ]
}}

Requirements:
- suggestions[].id must be unique simple strings like "s1", "s2", "s3".
- structuredResume.sections[].items[].id must be unique and used in suggestions[].targetItemId for rewrite_bullet.
- All suggestions must be about HARD TECHNICAL improvements, not soft skills.
- Return ONLY valid JSON with no comments.
            """.strip()

            try:
                completion = client.responses.create(
                    model="gpt-4.1-mini",
                    input=prompt,
                    response_format={"type": "json_object"}
                )
                raw = completion.output[0].content[0].text
                model_payload = json.loads(raw)

                suggestions_text = model_payload.get("personalSuggestionsText")
                lego_resume = model_payload.get("structuredResume")
                lego_suggestions = model_payload.get("suggestions")

            except Exception as e:
                logger.warning(f"OpenAI suggestions (Lego) failed: {e}")
                suggestions_text = None
                lego_resume = None
                lego_suggestions = None

        # Deduct credits
        try:
            supabase.table("profiles").update({"credits": credits - 1}).eq("user_id", uid).execute()
        except Exception as e:
            logger.error(f"Failed to deduct credits: {e}")
            # Don't fail - user already got analysis
            pass

        # Save to DB (now includes personal_suggestions + lego data)
        try:
            supabase.table("analyses").insert({
                "user_id": uid,
                "job_title": job_title,
                "fit_estimate": res.fit_estimate,
                "payload": {
                    "fit_estimate": res.fit_estimate,
                    "similarity_resume_job": res.sim_resume_jd,
                    "present_skills": present_skills,
                    "missing_skills": missing_skills,
                    "critical_gaps": critical_gaps,
                    "section_suggestions": section_suggestions,
                    "ready_bullets": ready_bullets,
                    "rewrite_hints": rewrite_hints,
                    "personal_suggestions": suggestions_text,
                    "lego_resume": lego_resume,
                    "lego_suggestions": lego_suggestions,
                },
                "resume_excerpt": resume_text[:300]
            }).execute()
        except Exception as e:
            logger.error(f"Failed to save analysis: {e}")

        logger.info(
            f"smart_analyze uid={uid} fit={res.fit_estimate} "
            f"missing={len(missing_skills)}"
        )

        return jsonify({
            "fit_estimate": res.fit_estimate,
            "similarity_resume_job": res.sim_resume_jd,
            "present_skills": present_skills,
            "missing_skills": missing_skills,
            "critical_gaps": critical_gaps,
            "section_suggestions": section_suggestions,
            "ready_bullets": ready_bullets,
            "rewrite_hints": rewrite_hints,

            # Old field your current UI uses:
            "personal_suggestions": suggestions_text,

            # === LEGO BLOCKS for new UI ===
            "lego_resume": lego_resume,
            "lego_suggestions": lego_suggestions,

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
       