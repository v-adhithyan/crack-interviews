"""Structured resume validation and rendering. User text never becomes HTML/CSS."""
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils.html import escape, format_html_join

MAX_BODY = 100_000
CONTACT = {"name": 120, "headline": 180, "email": 254, "phone": 60, "location": 120, "website": 200}
SECTIONS = {
    "skills": ({"label": 80, "items": 1200}, 12),
    "experience": ({"company": 150, "role": 150, "context": 180, "dates": 100, "bullets": 8000}, 15),
    "education": ({"school": 180, "degree": 180, "location": 120, "dates": 100}, 10),
}


def blank_content():
    return {"contact": {key: "" for key in CONTACT}, "summary": "", "skills": [], "experience": [], "education": []}


def fields(value, schema):
    if not isinstance(value, dict) or set(value) != set(schema):
        raise ValidationError("Unexpected or missing resume fields.")
    result = {}
    for key, limit in schema.items():
        item = value[key]
        if not isinstance(item, str) or len(item) > limit:
            raise ValidationError(f"{key} must contain at most {limit} characters.")
        if any(unicodedata.category(c) in {"Cc", "Cf"} and c not in "\n\r\t" for c in item):
            raise ValidationError(f"{key} contains unsupported control characters.")
        result[key] = item.strip()
    return result


def validate_content(content):
    if not isinstance(content, dict) or set(content) != {"contact", "summary", *SECTIONS}:
        raise ValidationError("Invalid resume structure.")
    result = {"contact": fields(content["contact"], CONTACT), **fields({"summary": content["summary"]}, {"summary": 3000})}
    for key, (schema, maximum) in SECTIONS.items():
        rows = content[key]
        if not isinstance(rows, list) or len(rows) > maximum:
            raise ValidationError(f"Use at most {maximum} {key} entries.")
        result[key] = [fields(row, schema) for row in rows]
    if len(json.dumps(result, ensure_ascii=False).encode()) > 60000:
        raise ValidationError("Resume content is too long (60 KB maximum).")
    if any(len(row['bullets'].splitlines()) > 30 for row in result['experience']):
        raise ValidationError("Use at most 30 bullet points per job.")
    return result


def emphasis(value):
    # Only **bold** is supported. Escape everything else, including HTML.
    parts = re.split(r"(\*\*[^*\n]+\*\*)", value)
    return format_html_join('', '{}', [(format_html_join('', '<strong>{}</strong>', [(part[2:-2],)]) if part.startswith('**') and part.endswith('**') else escape(part),) for part in parts])


def render_resume(content):
    content = validate_content(content)
    experience = [{**row, "points": [emphasis(line.lstrip('-• ').strip()) for line in row['bullets'].splitlines() if line.strip()]} for row in content['experience']]
    return render_to_string('product/resume_builder/document.html', {"resume_data": content, "experience": experience})


def render_pdf(content):
    if not validate_content(content)["contact"]["name"]:
        raise ValidationError("Enter your full name before exporting a resume.")
    html = render_resume(content)
    worker = Path(__file__).with_name('resume_pdf_worker.py')
    try:
        result = subprocess.run([sys.executable, str(worker)], input=html.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20, check=True)
    except (subprocess.SubprocessError, OSError) as exc:
        raise RuntimeError("PDF generation is temporarily unavailable. Your draft is saved; please try again.") from exc
    if not result.stdout.startswith(b'%PDF-') or len(result.stdout) > 5_000_000:
        raise RuntimeError("Unable to generate this PDF. Try shortening the resume.")
    return result.stdout
