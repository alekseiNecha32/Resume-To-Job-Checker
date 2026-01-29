"""
Pandoc-based resume export routes with template support.
"""
from flask import Blueprint, request, send_file, jsonify
import io

from app.services.resume_converter import (
    get_available_templates,
    generate_docx,
    generate_docx_fallback,
    PandocNotAvailableError,
    TemplateNotFoundError,
)

pandoc_export_bp = Blueprint("pandoc_export", __name__, url_prefix="/api/export")


@pandoc_export_bp.route("/templates", methods=["GET"])
def list_templates():
    """
    Get list of available resume templates.

    Returns:
        JSON with list of templates and their metadata.
    """
    templates = get_available_templates()
    return jsonify({"templates": templates})


@pandoc_export_bp.route("/resume-styled", methods=["POST"])
def export_styled_resume():
    """
    Generate a styled DOCX resume using the specified template.

    Request body:
        {
            "resume": { ... },
            "template_id": "classic" | "modern" | "compact"
        }

    Returns:
        DOCX file download.
    """
    data = request.get_json(silent=True) or {}
    resume = data.get("resume")
    template_id = data.get("template_id", "classic")

    if not resume:
        return jsonify({"error": "missing_resume"}), 400

    # Validate template_id
    valid_templates = ["classic", "modern", "compact"]
    if template_id not in valid_templates:
        return jsonify({
            "error": "invalid_template",
            "message": f"Template must be one of: {', '.join(valid_templates)}"
        }), 400

    try:
        # Try Pandoc first, fall back to python-docx if unavailable
        try:
            docx_bytes = generate_docx(resume, template_id)
        except PandocNotAvailableError:
            # Fallback to python-docx direct generation
            docx_bytes = generate_docx_fallback(resume, template_id)

        # Send file
        buf = io.BytesIO(docx_bytes)
        buf.seek(0)

        filename = f"resume_{template_id}.docx"

        return send_file(
            buf,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    except TemplateNotFoundError as e:
        return jsonify({"error": "template_not_found", "message": str(e)}), 404

    except Exception as e:
        return jsonify({"error": "export_failed", "message": str(e)}), 500
