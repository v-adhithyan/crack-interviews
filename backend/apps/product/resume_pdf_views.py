import logging
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from apps.core.jobs import enqueue_background_job
from .decorators import product_access_required
from .models import ResumeDraft, ResumePdfJob
from .resume_pdf_jobs import expire_stalled_jobs

logger = logging.getLogger(__name__)


@never_cache
@product_access_required
@require_POST
def export(request, draft_uuid):
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        draft = get_object_or_404(ResumeDraft, uuid=draft_uuid, user=request.user)
        if request.POST.get('revision') != str(draft.revision):
            return HttpResponse('Draft changed. Save or load the latest version before exporting.', status=409)
        if not draft.content.get('contact', {}).get('name'):
            return HttpResponse('Enter your full name before exporting a resume.', status=400)
        jobs = ResumePdfJob.objects.filter(draft__user=request.user)
        expire_stalled_jobs(jobs)
        now = timezone.now()
        job = jobs.filter(draft=draft, revision=draft.revision, expires_at__gt=now,
                          status__in=['queued', 'processing', 'ready']).order_by('-created_at').first()
        created = job is None
        if created:
            if jobs.filter(status__in=['queued', 'processing'], expires_at__gt=now).exists():
                return HttpResponse('Another PDF is being generated. Please wait for it to finish.', status=429)
            if jobs.filter(created_at__gte=now - timedelta(minutes=10)).count() >= 10:
                return HttpResponse('PDF export limit reached. Please try again in 10 minutes.', status=429)
            job = ResumePdfJob.objects.create(draft=draft, revision=draft.revision, content=draft.content,
                                              expires_at=now + timedelta(hours=1))
    # Publish only after commit: the worker can immediately read the snapshot.
    if created:
        try:
            enqueue_background_job('apps.product.resume_pdf_jobs.generate_resume_pdf', job.pk)
        except Exception:
            logger.exception('Unable to enqueue resume PDF job %s', job.uuid)
            ResumePdfJob.objects.filter(pk=job.pk, status='queued').update(status='failed', content={}, error='Unable to queue PDF. Please try again.')
    suffix = '?download=1' if request.POST.get('download') == '1' else ''
    return redirect(reverse('resume_pdf_detail', kwargs={'job_uuid': job.uuid}) + suffix)


def owned_job(request, job_uuid):
    job = get_object_or_404(ResumePdfJob.objects.select_related('draft'), uuid=job_uuid, draft__user=request.user)
    expire_stalled_jobs(ResumePdfJob.objects.filter(pk=job.pk))
    job.refresh_from_db()
    return job


def progress_data(job):
    state = 'expired' if job.expires_at <= timezone.now() else job.status
    stages = {
        'queued': ('PDF queued', 15, 'Waiting for a worker'),
        'processing': ('Generating your PDF', 60, 'Rendering the saved resume'),
        'ready': ('Your PDF is ready', 100, 'Completed'),
        'failed': ('PDF generation failed', None, 'Failed'),
        'expired': ('PDF expired', None, 'Expired'),
    }
    label, progress, stage = stages[state]
    return {'status': state, 'error': job.error, 'revision': job.revision,
            'label': label, 'progress': progress, 'stage': stage}


@never_cache
@product_access_required
@require_GET
def detail(request, job_uuid):
    job = owned_job(request, job_uuid)
    return render(request, 'product/resume_builder/pdf_job.html', {
        'job': job, 'progress': progress_data(job), 'download': request.GET.get('download') == '1', 'active_nav': 'resume_builder',
    })


@never_cache
@product_access_required
@require_GET
def status(request, job_uuid):
    job = owned_job(request, job_uuid)
    return JsonResponse(progress_data(job))


@never_cache
@product_access_required
@require_GET
def file(request, job_uuid):
    job = owned_job(request, job_uuid)
    if job.expires_at <= timezone.now():
        return HttpResponse('This PDF has expired. Request a new export.', status=410)
    if job.status != 'ready' or not job.file:
        return HttpResponse('PDF is not ready.', status=409)
    try:
        stream = job.file.open('rb')
    except FileNotFoundError:
        ResumePdfJob.objects.filter(pk=job.pk).update(status='failed', error='PDF file is no longer available. Request a new export.')
        return HttpResponse('PDF is no longer available. Request a new export.', status=410)
    response = FileResponse(stream, content_type='application/pdf', filename='resume.pdf', as_attachment=request.GET.get('download') == '1')
    response['X-Content-Type-Options'] = 'nosniff'
    return response
