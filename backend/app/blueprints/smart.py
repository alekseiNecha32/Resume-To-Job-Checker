from flask import Blueprint, current_app, request, jsonify
from app.services.smart_resume_advisor import smart_predict_resume_improvements
from supabase import create_client
import os
from dotenv import load_dotenv
import logging
import json
from uuid import uuid4 
from app.services.suggestion_safety import enforce_no_fake_metrics

smart_bp = Blueprint("smart", __name__, url_prefix="/api/smart")
logger = logging.getLogger(__name__)

_HEADER_USER_ID = "X-User-Id"
_HEADER_AUTH = "Authorization"

def get_user_id():
    return request.headers.get(_HEADER_USER_ID)



def _resume_json_to_text(resume_json: dict) -> str:
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
    resume_text = _resume_json_to_text(resume)

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
        suggestions = enforce_no_fake_metrics(fallback_list(), resume_text)
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
        suggestions = enforce_no_fake_metrics(suggestions, resume_text)
        if isinstance(suggestions, list):
            suggestions = suggestions[:5]
    except Exception as e:
        logger.warning("suggest fallback: %s", e)
        suggestions = enforce_no_fake_metrics(fallback_list(), resume_text)

    return jsonify({"suggestions": suggestions})


def _resolve_uid(supabase):
    uid = request.headers.get(_HEADER_USER_ID)
    if uid:
        return uid
    auth = request.headers.get(_HEADER_AUTH) or ""
    if not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    try:
        if hasattr(supabase.auth, "get_user"):
            uresp = supabase.auth.get_user(token)
            if isinstance(uresp, dict):
                user = (uresp.get("data") or {}).get("user")
            else:
                user = getattr(uresp, "user", None)
        elif hasattr(supabase.auth, "api") and hasattr(supabase.auth.api, "get_user"):
            uresp = supabase.auth.api.get_user(token)
            user = (uresp.get("data") or {}).get("user") if isinstance(uresp, dict) else getattr(uresp, "user", None)
        else:
            return None
        if user:
            return user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    except Exception:
        pass
    return None


def _make_supabase():
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


@smart_bp.route("/analyze", methods=["POST", "OPTIONS"])
def analyze():
    """Phase 1 — ML analysis only. Returns fit/skills/gaps immediately and deducts one credit."""
    if request.method == "OPTIONS":
        return ("", 204)
    try:
        supabase = _make_supabase()
        if not supabase:
            return jsonify({"error": "server_misconfigured"}), 500

        uid = _resolve_uid(supabase)
        if not uid:
            return jsonify({"error": "Unauthorized"}), 401

        profile_res = supabase.table("profiles").select("credits").eq("user_id", uid).execute()
        pdata_raw = getattr(profile_res, "data", None) or (profile_res.get("data") if isinstance(profile_res, dict) else None)
        pdata = (pdata_raw[0] if isinstance(pdata_raw, list) else pdata_raw) or {}
        credits = pdata.get("credits", 0)

        if credits <= 0:
            return jsonify({"error": "no_credits", "message": "Please purchase credits to use Smart Analysis."}), 402

        d = request.get_json(force=True)
        if not d or not d.get("resume_text") or not d.get("job_text"):
            return jsonify({"error": "Missing resume_text or job_text"}), 400

        resume_text = d.get("resume_text", "")
        job_text = d.get("job_text", "")
        job_title = d.get("job_title", "")

        res = smart_predict_resume_improvements(
            resume_text=resume_text,
            job_text=job_text,
            job_title=job_title
        )
        if res is None:
            return jsonify({"error": "Analysis failed"}), 500

        present_skills = res.present_skills or []
        missing_skills = res.missing_skills or []
        critical_gaps = res.critical_gaps or []
        section_suggestions = res.section_suggestions or {}
        ready_bullets = res.ready_bullets or []
        rewrite_hints = res.rewrite_hints or []

        try:
            supabase.table("profiles").update({"credits": credits - 1}).eq("user_id", uid).execute()
        except Exception:
            logger.exception("Failed to deduct credits")

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
                },
                "resume_excerpt": resume_text[:300]
            }).execute()
        except Exception:
            logger.exception("Failed to save analysis")

        return jsonify({
            "fit_estimate": res.fit_estimate,
            "similarity_resume_job": res.sim_resume_jd,
            "present_skills": present_skills,
            "missing_skills": missing_skills,
            "critical_gaps": critical_gaps,
            "section_suggestions": section_suggestions,
            "ready_bullets": ready_bullets,
            "rewrite_hints": rewrite_hints,
            "remaining_credits": credits - 1,
        }), 200

    except Exception:
        logger.exception("smart_analyze error")
        return jsonify({"error": "internal_server_error"}), 500


@smart_bp.route("/enrich", methods=["POST", "OPTIONS"])
def enrich():
    """Phase 2 — OpenAI suggestions only. No credit deduction. Called after /analyze returns."""
    if request.method == "OPTIONS":
        return ("", 204)
    try:
        supabase = _make_supabase()
        if not supabase:
            return jsonify({"error": "server_misconfigured"}), 500

        uid = _resolve_uid(supabase)
        if not uid:
            return jsonify({"error": "Unauthorized"}), 401

        d = request.get_json(force=True) or {}
        resume_text = d.get("resume_text", "")
        job_text = d.get("job_text", "")
        job_title = d.get("job_title", "")
        present_skills = d.get("present_skills", [])
        missing_skills = d.get("missing_skills", [])
        critical_gaps = d.get("critical_gaps", [])

        client = current_app.config.get("OPENAI_CLIENT")
        if not client:
            return jsonify({"personal_suggestions": None, "lego_resume": None, "lego_suggestions": None}), 200

        prompt = f'''
You are an ATS expert and resume editor.

Your job is to analyze the resume and job description and propose improvements focused ONLY on hard technical skills, tools, frameworks, and concrete deliverables.

IMPORTANT RULES:
- Focus on things like programming languages, frameworks, libraries, tools, cloud, testing, automation, CI/CD, data/ML.
- IGNORE soft skills like communication, teamwork, cross time zone collaboration, leadership, culture fit, etc.
- Do not suggest generic "team player", "strong communication", "fast learner", etc.
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
"""{resume_text[:3500]}"""

Job description (raw text):
"""{job_text[:3500]}"""

Return a SINGLE JSON object with this structure:

{{
  "personalSuggestionsText": "string with 4-6 short bullet points in markdown style, each starting with \'- \' and all about hard technical improvements",

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
        '''.strip()

        suggestions_text = None
        lego_resume = None
        lego_suggestions = None

        try:
            completion = client.responses.create(
                model="gpt-4.1-mini",
                input=prompt,
                text={"format": {"type": "json_object"}}
            )
            raw = completion.output[0].content[0].text
            model_payload = json.loads(raw)

            suggestions_text = model_payload.get("personalSuggestionsText")
            lego_resume = model_payload.get("structuredResume")
            lego_suggestions = model_payload.get("suggestions")

            if isinstance(lego_suggestions, list):
                lego_suggestions = enforce_no_fake_metrics(lego_suggestions, resume_text)
                lego_suggestions = lego_suggestions[:5]
        except Exception:
            logger.exception("OpenAI enrich failed")

        return jsonify({
            "personal_suggestions": suggestions_text,
            "lego_resume": lego_resume,
            "lego_suggestions": lego_suggestions,
        }), 200

    except Exception:
        logger.exception("smart_enrich error")
        return jsonify({"error": "internal_server_error"}), 500
