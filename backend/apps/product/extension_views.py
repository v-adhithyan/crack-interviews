"""Same-origin, session/CSRF-protected endpoints for the browser extension bridge.

No CORS exemptions or extension bearer tokens. Chrome executes the fetch in an
isolated world on the signed-in HackerLeap connection tab.
"""
import hashlib
import json
import logging
from datetime import timedelta
from functools import wraps
from urllib.parse import urlsplit
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from apps.core.jobs import enqueue_background_job
from .decorators import product_access_required, user_has_product_access
from .forms import AnalysisPromptForm
from .models import Resume, ResumeAnalysis, ResumeDraft, UserFeatureFlags
from .resume_builder import validate_content
from .services import build_resume_match_prompt, get_effective_resume_analysis_mode, reserve_resume_analysis_ai_quota

logger = logging.getLogger(__name__)
SALT = 'hackerleap.extension.resume-selection.v1'


def api_access(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'detail': 'Sign in to HackerLeap, then reconnect the extension.'}, status=401)
        if not user_has_product_access(request.user):
            return JsonResponse({'detail': 'Your account does not have access to resume analysis.'}, status=403)
        return view(request, *args, **kwargs)
    return wrapped


def selection(user, kind, identifier, revision):
    return signing.dumps({'user': user.pk, 'kind': kind, 'id': str(identifier), 'revision': revision}, salt=SALT)


def uploaded_revision(resume):
    # Invalidates selection even if the resume was replaced within one timestamp tick.
    return hashlib.sha256(json.dumps([str(resume.updated_at), resume.parsed_text, resume.builder_snapshot], sort_keys=True).encode()).hexdigest()


def draft_text(content):
    content = validate_content(content)
    lines = [v for v in content['contact'].values() if v]
    if not content['contact']['name']:
        raise ValidationError('Add your name to the saved resume before analysis.')
    if content['summary']:
        lines += ['Professional Summary', content['summary']]
    for key, heading in [('skills', 'Skills'), ('experience', 'Work History'), ('projects', content.get('projects_heading', 'Projects')), ('education', 'Education')]:
        if content.get(key):
            lines.append(heading)
            for row in content[key]:
                lines.extend(v for v in row.values() if v)
    return '\n'.join(lines)


@never_cache
@product_access_required
@require_GET
def bridge(request):
    return render(request, 'product/extension_bridge.html')


@never_cache
@api_access
@require_GET
def resumes(request):
    rows = []
    for draft in ResumeDraft.objects.filter(user=request.user).order_by('-updated_at'):
        rows.append({'id': str(draft.uuid), 'kind': 'draft', 'title': draft.title, 'revision': draft.revision,
                     'selection': selection(request.user, 'draft', draft.uuid, draft.revision)})
    resume = Resume.objects.filter(user=request.user).first()
    if resume and resume.parsed_text.strip():
        rows.append({'id': str(resume.uuid), 'kind': 'uploaded', 'title': 'Currently selected: ' + resume.original_filename,
                     'revision': uploaded_revision(resume), 'selection': selection(request.user, 'uploaded', resume.uuid, uploaded_revision(resume))})
    return JsonResponse({'resumes': rows, 'csrf_token': get_token(request), 'account': request.user.get_username(),
                         'mode': 'chatgpt' if get_effective_resume_analysis_mode(request.user) == 'chatgpt' else 'manual'})


@never_cache
@api_access
@require_POST
def submit(request):
    if request.content_type != 'application/json' or len(request.body) > 100_000:
        return JsonResponse({'detail': 'Send a JSON request under 100 KB.'}, status=400)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) != {'selection', 'request_id', 'job'}:
            raise ValueError()
        key = UUID(data['request_id'])
        chosen = signing.loads(data['selection'], salt=SALT, max_age=1800)
        if chosen['user'] != request.user.pk:
            return JsonResponse({'detail': 'The signed-in account changed. Reload resumes.'}, status=409)
        job = data['job']
        if not isinstance(job, dict) or set(job) != {'title', 'company', 'description', 'url', 'source'}:
            raise ValueError()
        for field, limit in [('title', 200), ('company', 200), ('description', 12000), ('url', 2000), ('source', 20)]:
            if not isinstance(job[field], str) or len(job[field]) > limit or '\x00' in job[field]:
                raise ValueError()
        if job['source'] not in {'ashby', 'greenhouse', 'manual'}:
            raise ValueError()
        if job['url']:
            url = urlsplit(job['url'])
            if url.scheme != 'https' or not url.hostname or url.username or url.password or any(c.isspace() for c in job['url']):
                raise ValueError()
        form = AnalysisPromptForm({'job_description': job['description']})
        if not form.is_valid():
            raise ValidationError('Enter a job description of at most 12,000 characters.')
        context = [f"Job title: {job['title'].strip()}" if job['title'].strip() else '',
                   f"Company: {job['company'].strip()}" if job['company'].strip() else '']
        description = '\n'.join(line for line in context if line) + '\n\n' + form.cleaned_data['job_description']
        description = description.strip()
        digest = hashlib.sha256(json.dumps({'selection': chosen, 'job': job}, sort_keys=True).encode()).hexdigest()
    except (ValueError, TypeError, KeyError, AttributeError, signing.BadSignature, ValidationError, RecursionError) as exc:
        detail = ' '.join(exc.messages) if isinstance(exc, ValidationError) else 'Invalid or expired selection. Reload resumes and check the job description.'
        return JsonResponse({'detail': detail}, status=400)

    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        existing = ResumeAnalysis.objects.filter(user=request.user, submission_key=key).first()
        if existing:
            if existing.submission_digest != digest:
                return JsonResponse({'detail': 'This request ID was already used for different inputs.'}, status=409)
            return analysis_response(existing)
        if ResumeAnalysis.objects.filter(user=request.user, submission_key__isnull=False,
                created_at__gte=timezone.now()-timedelta(hours=24)).count() >= 20:
            return JsonResponse({'detail': 'Extension limit reached: 20 analyses per 24 hours.'}, status=429)
        resume = None
        if chosen['kind'] == 'draft':
            draft = ResumeDraft.objects.select_for_update().filter(user=request.user, uuid=chosen['id']).first()
            if not draft or draft.revision != chosen['revision']:
                return JsonResponse({'detail': 'The resume changed or was deleted. Reload resumes and select it again.'}, status=409)
            try:
                text = draft_text(draft.content)
            except ValidationError as exc:
                return JsonResponse({'detail': ' '.join(exc.messages)}, status=400)
            snapshot = {'draft_uuid': str(draft.uuid), 'revision': draft.revision, 'template_version': draft.template_version,
                        'title': draft.title, 'content': draft.content}
        elif chosen['kind'] == 'uploaded':
            resume = Resume.objects.select_for_update().filter(user=request.user, uuid=chosen['id']).first()
            if not resume or uploaded_revision(resume) != chosen['revision']:
                return JsonResponse({'detail': 'Your selected resume changed. Reload resumes.'}, status=409)
            text, snapshot = resume.parsed_text, resume.builder_snapshot
        else:
            return JsonResponse({'detail': 'Unsupported resume selection.'}, status=400)
        # Serialize quota consumption with other code that locks feature flags.
        UserFeatureFlags.objects.select_for_update().filter(user=request.user).first()
        automatic = get_effective_resume_analysis_mode(request.user) == 'chatgpt' and reserve_resume_analysis_ai_quota(request.user)
        analysis = ResumeAnalysis.objects.create(user=request.user, resume=resume, resume_text=text, builder_snapshot=snapshot,
            job_description=description, generated_prompt=build_resume_match_prompt(description, text, snapshot),
            status='queued' if automatic else 'prompt_ready', ai_provider='chatgpt' if automatic else 'manual',
            submission_key=key, submission_digest=digest)
    if automatic:
        try:
            task_id = enqueue_background_job('apps.product.tasks.run_resume_analysis', analysis.pk)
            ResumeAnalysis.objects.filter(pk=analysis.pk).update(task_id=task_id or '')
        except Exception as exc:
            logger.error('Extension analysis enqueue failed analysis=%s exception_type=%s', analysis.uuid, type(exc).__name__)
            analysis.status = 'failed'
            ResumeAnalysis.objects.filter(pk=analysis.pk).update(status='failed', error_message='Unable to queue analysis. Your prompt is saved.', updated_at=timezone.now())
    return analysis_response(analysis, 201)


def analysis_response(analysis, status=200):
    return JsonResponse({'analysis_id': str(analysis.uuid), 'status': analysis.status,
                         'url': reverse('analysis_detail', kwargs={'analysis_uuid': analysis.uuid})}, status=status)
