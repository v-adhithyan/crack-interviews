import hashlib
import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse, JsonResponse, FileResponse
from django.utils.text import slugify
from django.template.loader import render_to_string
from django.core.cache import cache
from io import BytesIO

from .resume_builder import render_document_pdf
from .resume_fonts import FAMILIES, faces
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_GET

from apps.core.jobs import enqueue_background_job
from .decorators import product_access_required
from .models import ResumeAnalysis, AnalysisFollowup
from .followups import clean_questions, build_prompt, parse_result
from .services import get_effective_resume_analysis_mode, reserve_resume_analysis_ai_quota


def owned_analysis(request, analysis_uuid):
    return get_object_or_404(ResumeAnalysis, uuid=analysis_uuid, user=request.user,
                            status=ResumeAnalysis.Status.RESULT_ADDED)


def expire_stalled(job):
    if job.status in {'queued', 'processing'} and job.updated_at < timezone.now() - timedelta(minutes=5):
        AnalysisFollowup.objects.filter(pk=job.pk, status=job.status, updated_at=job.updated_at).update(status='failed', updated_at=timezone.now())
        job.refresh_from_db()


@never_cache
@product_access_required
@require_http_methods(['GET', 'POST'])
def create(request, analysis_uuid):
    analysis = owned_analysis(request, analysis_uuid)
    questions, cover, error = [''], False, ''
    if request.method == 'POST':
        questions = request.POST.getlist('questions')
        cover = request.POST.get('cover_letter') == 'on'
        try:
            questions = clean_questions(questions)
            prompt = build_prompt(analysis, questions, cover)
            key = hashlib.sha256(prompt.encode()).hexdigest()
            with transaction.atomic():
                get_user_model().objects.select_for_update().get(pk=request.user.pk)
                job = AnalysisFollowup.objects.filter(analysis=analysis, request_key=key).first()
                if job:
                    return redirect('analysis_followup_detail', job_uuid=job.uuid)
                if AnalysisFollowup.objects.filter(analysis__user=request.user, created_at__gte=timezone.now()-timedelta(hours=24)).count() >= 20:
                    raise ValidationError('You can create up to 20 follow-up batches per 24 hours.')
                automatic = get_effective_resume_analysis_mode(request.user) == 'chatgpt' and reserve_resume_analysis_ai_quota(request.user)
                job = AnalysisFollowup.objects.create(analysis=analysis, request_key=key, questions=questions,
                    include_cover_letter=cover, prompt=prompt, status='queued' if automatic else 'manual')
            if automatic:
                try:
                    enqueue_background_job('apps.product.followups.run_followup', job.pk)
                except Exception:
                    AnalysisFollowup.objects.filter(pk=job.pk, status='queued').update(status='failed')
            return redirect('analysis_followup_detail', job_uuid=job.uuid)
        except ValidationError as exc:
            error = ' '.join(exc.messages)
    return render(request, 'product/followups.html', dict(analysis=analysis, questions=questions[:10] or [''], cover=cover,
        error=error, active_nav='analysis', history=analysis.followups.all()[:20]))


@never_cache
@product_access_required
@require_http_methods(['GET', 'POST'])
def detail(request, job_uuid):
    job = get_object_or_404(AnalysisFollowup.objects.select_related('analysis'), uuid=job_uuid, analysis__user=request.user)
    expire_stalled(job)
    error, raw = '', ''
    if request.method == 'POST':
        if job.status not in {'manual', 'failed'}:
            return HttpResponse('This response is already saved or still processing.', status=409)
        raw = request.POST.get('response_json', '')
        try:
            result = parse_result(raw, job)
            if not AnalysisFollowup.objects.filter(pk=job.pk, status__in=['manual', 'failed']).update(result=result, status='ready', updated_at=timezone.now()):
                return HttpResponse('This response changed. Reload the page.', status=409)
            return redirect('analysis_followup_detail', job_uuid=job.uuid)
        except ValidationError as exc:
            error = ' '.join(exc.messages)
    answers = [dict(question=q, answer=a['answer']) for q, a in zip(job.questions, job.result.get('answers', []))]
    return render(request, 'product/followups.html', dict(job=job, analysis=job.analysis, answers=answers, error=error,
        raw=raw[:100000], active_nav='analysis'))


@never_cache
@product_access_required
@require_GET
def status(request, job_uuid):
    job = get_object_or_404(AnalysisFollowup, uuid=job_uuid, analysis__user=request.user)
    expire_stalled(job)
    return JsonResponse({'status': job.status})


@never_cache
@product_access_required
@require_GET
def cover_letter_pdf(request, job_uuid):
    job = get_object_or_404(AnalysisFollowup.objects.select_related('analysis'), uuid=job_uuid,
                           analysis__user=request.user, status='ready', include_cover_letter=True)
    letter = job.result.get('cover_letter') if isinstance(job.result, dict) else None
    if not isinstance(letter, str) or not letter.strip() or len(letter) > 12000:
        return HttpResponse('No valid cover letter is available for this response.', status=404)
    if not cache.add(f'cover-letter-export:{request.user.pk}', True, timeout=5):
        return HttpResponse('Please wait a few seconds before downloading another PDF.', status=429)
    html = render_to_string('product/cover_letter_pdf.html', {
        'letter': letter,
        'font_faces': [{'url': 'resume-font:' + name, 'style': style, 'weight': weight}
                       for name, style, weight in faces(FAMILIES['default'])],
    })
    try:
        pdf = render_document_pdf(html)
    except RuntimeError:
        return HttpResponse('Unable to generate the cover letter PDF right now. Please try again.', status=503)
    username = slugify(request.user.get_username())[:80] or 'user'
    company = job.analysis.result_data.get('company_detected')
    company = slugify(company if isinstance(company, str) else '')[:80] or 'company'
    filename = f'{username}_{company}_cover_letter.pdf'
    return FileResponse(BytesIO(pdf), as_attachment=True, filename=filename, content_type='application/pdf')
