from flask import Blueprint, current_app, request, jsonify
from app.services.smart_resume_advisor import smart_predict_resume_improvements
from supabase import create_client
import os
from dotenv import load_dotenv
import logging
import json
from uuid import uuid4 
from app.services.suggestion_safety import enforce_no_fake_metrics  # NEWenforce_no_fake_metrics

smart_bp = Blueprint("smart", __name__, url_prefix="/api/smart")
logger = logging.getLogger(__name__)

def get_user_id():
    return request.headers.get("X-User-Id")



def _resume_json_to_text(resume_json: dict) -> str:
    """
    Best-effort flattening for metric safety checks.
    """
    if not isinstance(resume_json, dict):
        return ""
    parts = []
    for sec in (resume_json.get("sections") or []):
        title = sec.get("title")
        if title:
            parts.append(str(title))
        for it in (sec.get("items") or []):
            txt = it.get("text") if isinstance(it, dict) else None
            if txt:
                parts.append(str(txt))
    return "\n".join(parts)

@smart_bp.post("/suggest")
def suggest():
    body = request.get_json(force=True) or {}
    resume = body.get("resume") or {}
    job_text = (body.get("jobText") or "")[:4000]
    resume_text = _resume_json_to_text(resume)  # NEW

    def fallback_list():
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
            # NEW: two extra fallback suggestions (kept simple)
            {
                "id": f"add2-{uuid4()}",
                "type": "add_bullet",
                "targetSectionId": first_sec.get("id", "experience"),
                "suggestedText": "Automated recurring reporting tasks with scripts and scheduling to reduce manual effort.",
                "reason": "Adds concrete automation impact without inventing numbers."
            },
            {
                "id": f"proj2-{uuid4()}",
                "type": "project_idea",
                "targetSectionId": "projects",
                "suggestedText": "Monitoring mini-project: add structured logs, dashboards, and alert thresholds for a small API.",
                "reason": "Demonstrates reliability/observability skills."
            },
        ]

    client = current_app.config.get("OPENAI_CLIENT")
    if not client:
        suggestions = enforce_no_fake_metrics(fallback_list(), resume_text)  # NEW
        return jsonify({"suggestions": suggestions})

    prompt = f"""
You generate resume edit suggestions.

Resume JSON: {resume}
Job: {job_text}

Return JSON array of 5 suggestions.

Hard rules:
- Do NOT invent numbers/metrics. Only use numbers if they already appear somewhere in the Resume JSON.
  If no numbers exist in the resume, write impact without numbers (e.g., "helped reduce", "aimed to improve").
- Do NOT claim experience with tools/terms not evidenced in the resume. If not evidenced, phrase as learning/familiarity/interest.

Each object:
- id: string
- type: add_bullet | rewrite_bullet | project_idea
- targetSectionId: existing section id or "projects"
- targetItemId: only for rewrite_bullet
- originalText: for rewrite_bullet
- suggestedText: concise, hard-skill focused
- reason: short reason
JSON only.
""".strip()

    try:
        completion = client.responses.create(
            model="gpt-4.1-mini",
            input=[{"role": "user", "content": prompt}],
            max_output_tokens=1200,
        )
        raw = completion.output[0].content[0].text
        suggestions = json.loads(raw)

        # NEW: enforce metric safety deterministically server-side
        suggestions = enforce_no_fake_metrics(suggestions, resume_text)

        # Optional guard: keep at most 5
        if isinstance(suggestions, list):
            suggestions = suggestions[:5]
    except Exception as e:
        logger.warning("suggest fallback: %s", e)
        suggestions = enforce_no_fake_metrics(fallback_list(), resume_text)  # NEW

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
- Do NOT invent numbers/metrics. Only use numbers if they already appear in the resume text.
  If the resume contains no numbers, write impact without numbers (e.g., "helped reduce", "aimed to improve").
- Do NOT claim experience with tools/terms not evidenced in the resume. If not evidenced, phrase as learning/familiarity/interest.

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
    ]
  }},

  "suggestions": [
    {{
      "id": "s1",
      "type": "add_bullet",
      "targetSectionId": "experience",
      "targetItemId": null,
      "title": "Add hard-skill impact bullet",
      "originalText": null,
      "suggestedText": "Built CI checks for a .NET API using GitHub Actions to improve release confidence and reduce regressions.",
      "reason": "Adds concrete tooling and delivery signals without inventing metrics."
    }}
  ]
}}

Requirements:
- Return EXACTLY 5 suggestions in suggestions[] (s1..s5).
- suggestions[].id must be unique simple strings like "s1", "s2", "s3", "s4", "s5".
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

                # NEW: enforce metric safety + cap to 5
                if isinstance(lego_suggestions, list):
                    lego_suggestions = enforce_no_fake_metrics(lego_suggestions, resume_text)
                    lego_suggestions = lego_suggestions[:5]

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
                    
   