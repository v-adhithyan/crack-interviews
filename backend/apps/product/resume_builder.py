"""Structured resume validation and rendering. User text never becomes HTML/CSS."""
import json
import logging
import os
import re
import subprocess
import sys
import unicodedata
from time import monotonic
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.template.loader import render_to_string
from django.templatetags.static import static

from .resume_fonts import FAMILIES, faces
from django.utils.html import escape, format_html_join

logger = logging.getLogger(__name__)

FONT_CHOICES = {
    'default': 'Liberation Sans (default)', 'calibri': 'Carlito (Calibri alternative)', 'arial': 'Liberation Sans (Arial alternative)',
    'helvetica': 'Liberation Sans (Helvetica alternative)', 'garamond': 'EB Garamond',
    'cambria': 'Caladea (Cambria alternative)', 'georgia': 'Liberation Serif (Georgia alternative)',
}
DEFAULT_TYPOGRAPHY = {'font': 'default', 'body_size': 10.5, 'heading_size': 12, 'name_size': 22}
SIZE_CHOICES = {
    'body_size': [n / 2 for n in range(18, 29)],
    'heading_size': [n / 2 for n in range(20, 37)],
    'name_size': list(range(18, 33)),
}


def validate_typography(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULT_TYPOGRAPHY):
        raise ValidationError('Invalid resume font settings.')
    if not isinstance(value['font'], str) or value['font'] not in FONT_CHOICES:
        raise ValidationError('Choose a supported resume font.')
    for key, choices in SIZE_CHOICES.items():
        if type(value[key]) not in (int, float) or value[key] not in choices:
            raise ValidationError(f'Choose a supported {key.replace("_", " ")}.')
    return dict(value)


MAX_BODY = 100_000
CONTACT = {"name": 120, "headline": 180, "email": 254, "phone": 60, "location": 120, "website": 200}
SECTIONS = {
    "skills": ({"label": 80, "items": 1200}, 12),
    "experience": ({"company": 150, "role": 150, "context": 180, "dates": 100, "bullets": 8000}, 15),
    "projects": ({"name": 180, "website": 500, "start_year": 4, "end_year": 7, "bullets": 8000}, 15),
    "education": ({"school": 180, "degree": 180, "location": 120, "dates": 100}, 10),
}


def blank_content():
    return {"contact": {key: "" for key in CONTACT}, "summary": "", "skills": [], "experience": [], "education": [], "projects": [], "projects_heading": "Projects", "typography": dict(DEFAULT_TYPOGRAPHY)}


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
    if not isinstance(content, dict) or set(content) - {"typography", "projects", "projects_heading"} != {"contact", "summary", "skills", "experience", "education"}:
        raise ValidationError("Invalid resume structure.")
    result = {"contact": fields(content["contact"], CONTACT), **fields({"summary": content["summary"]}, {"summary": 3000})}
    for key, (schema, maximum) in SECTIONS.items():
        if key == "projects" and key not in content:
            continue
        rows = content[key]
        if not isinstance(rows, list) or len(rows) > maximum:
            raise ValidationError(f"Use at most {maximum} {key} entries.")
        result[key] = [fields(row, schema) for row in rows]
    if 'projects_heading' in content:
        result.update(fields({'projects_heading': content['projects_heading']}, {'projects_heading': 80}))
        if not result['projects_heading'] or '\n' in result['projects_heading'] or '\r' in result['projects_heading']:
            raise ValidationError('Enter a section heading on one line.')
    for project in result.get('projects', []):
        for key in ('start_year', 'end_year'):
            year = project[key]
            if year and not (key == 'end_year' and year == 'Present') and not re.fullmatch(r'[1-9][0-9]{3}', year):
                raise ValidationError('Use a four-digit year, or Present for the end year.')
        if project['start_year'] and project['end_year'] not in ('', 'Present') and project['end_year'] < project['start_year']:
            raise ValidationError('Project end year cannot be before its start year.')
        if project['website']:
            try:
                URLValidator(schemes=['https', 'http'])(project['website'])
                url = urlsplit(project['website'])
                if url.username or url.password:
                    raise ValidationError('Credentials are not allowed in project websites.')
            except ValueError as exc:
                raise ValidationError('Enter a valid project website URL.') from exc
        if len(project['bullets'].splitlines()) > 30:
            raise ValidationError('Use at most 30 bullet points per project.')
    if 'typography' in content:
        result['typography'] = validate_typography(content['typography'])
    if len(json.dumps(result, ensure_ascii=False).encode()) > 60000:
        raise ValidationError("Resume content is too long (60 KB maximum).")
    if any(len(row['bullets'].splitlines()) > 30 for row in result['experience']):
        raise ValidationError("Use at most 30 bullet points per job.")
    return result


def emphasis(value):
    # Only **bold** is supported. Escape everything else, including HTML.
    parts = re.split(r"(\*\*[^*\n]+\*\*)", value)
    return format_html_join('', '{}', [(format_html_join('', '<strong>{}</strong>', [(part[2:-2],)]) if part.startswith('**') and part.endswith('**') else escape(part),) for part in parts])


def render_resume(content, *, for_pdf=False):
    content = validate_content(content)
    experience = [{**row, "points": [emphasis(line.lstrip('-• ').strip()) for line in row['bullets'].splitlines() if line.strip()]} for row in content['experience']]
    projects = [{**row, "points": [emphasis(line.lstrip('-• ').strip()) for line in row['bullets'].splitlines() if line.strip()]} for row in content.get('projects', [])]
    website = content['contact']['website'].strip()
    linkedin_url = ''
    candidate = website if '://' in website else 'https://' + website
    try:
        parsed = urlsplit(candidate)
        host = (parsed.hostname or '').lower()
        if (parsed.scheme in {'https', 'http'} and not parsed.username and not parsed.password
                and (host == 'linkedin.com' or host.endswith('.linkedin.com'))
                and not any(char.isspace() for char in website)):
            linkedin_url = candidate
    except ValueError:
        pass
    typography = content.get('typography', DEFAULT_TYPOGRAPHY)
    typography = {key: format(value, 'g') if key != 'font' else value for key, value in typography.items()}
    family = FAMILIES[typography['font']]
    font_faces = [{'url': 'resume-font:' + name if for_pdf else static('product/fonts/' + name),
                   'style': style, 'weight': weight} for name, style, weight in faces(family)]
    return render_to_string('product/resume_builder/document.html', {"resume_data": content, "experience": experience, "projects": projects, "linkedin_url": linkedin_url, "typography": typography, "font_faces": font_faces})


def pdf_python_executable():
    # Embedded servers (notably uWSGI) expose the server binary as sys.executable.
    # Keep the venv path intact: resolving its symlink would lose venv packages.
    configured = getattr(settings, 'RESUME_PDF_PYTHON', '')
    interpreter = Path(configured) if configured else Path(sys.prefix) / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not interpreter.is_absolute() or not interpreter.is_file() or not os.access(interpreter, os.X_OK):
        raise OSError('PDF Python interpreter is unavailable. Set RESUME_PDF_PYTHON to the absolute virtualenv Python path.')
    return str(interpreter)


def render_pdf(content):
    if not validate_content(content)["contact"]["name"]:
        raise ValidationError("Enter your full name before exporting a resume.")
    return render_document_pdf(render_resume(content, for_pdf=True))


def render_document_pdf(html):
    """Render trusted template HTML using the bounded, resource-restricted worker."""
    worker = Path(__file__).with_name('resume_pdf_worker.py')
    started = monotonic()
    interpreter = '(not resolved)'
    try:
        interpreter = pdf_python_executable()
        logger.info('PDF renderer starting python=%s worker=%s', interpreter, worker)
        result = subprocess.run([interpreter, str(worker)], input=html.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20, check=True)
    except (subprocess.SubprocessError, OSError) as exc:
        stderr = getattr(exc, 'stderr', None) or b''
        if isinstance(stderr, bytes):
            stderr = stderr.decode('utf-8', errors='replace')
        logger.exception('PDF generation failed python=%s returncode=%s timeout=%s elapsed_seconds=%.2f. Renderer stderr: %s', interpreter, getattr(exc, 'returncode', None), getattr(exc, 'timeout', None), monotonic() - started, stderr[-8000:] or '(unavailable)')
        raise RuntimeError("PDF generation is temporarily unavailable. Your draft is saved; please try again.") from exc
    if not result.stdout.startswith(b'%PDF-') or len(result.stdout) > 5_000_000:
        logger.error('PDF renderer returned invalid output python=%s size=%d bytes elapsed_seconds=%.2f stderr=%s', interpreter, len(result.stdout), monotonic() - started, result.stderr.decode('utf-8', errors='replace')[-8000:])
        raise RuntimeError("Unable to generate this PDF. Try shortening the resume.")
    for line in result.stderr.decode('utf-8', errors='replace').splitlines():
        if line.startswith('PDF_METRICS '):
            try:
                stats = json.loads(line[len('PDF_METRICS '):])
                if set(stats) == {'peak_memory_bytes', 'cpu_ms', 'pages'} and all(type(value) is int and value >= 0 for value in stats.values()):
                    logger.info('PDF renderer resources peak_memory_bytes=%d cpu_ms=%d pages=%d', stats['peak_memory_bytes'], stats['cpu_ms'], stats['pages'])
            except (ValueError, TypeError):
                pass
    return result.stdout
