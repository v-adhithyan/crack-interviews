"""Public editor: transient previews, session-owned exports and explicit account handoff."""
import hashlib
import json
import logging
import secrets
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse, JsonResponse, FileResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from apps.core.jobs import enqueue_background_job
from apps.website.models import EarlyAccessUser
from .models import (PublicBuilderGate, PublicBuilderCounter, PublicResumeTransfer,
                     PublicResumePdfJob, ResumePdfJob, ResumeDraft, UserFeatureFlags)
from .resume_builder import blank_content, validate_content, render_resume, DEFAULT_TYPOGRAPHY, fields
from .resume_builder_views import payload, error
from .resume_pdf_jobs import expire_stalled_jobs
from .resume_pdf_views import progress_data
from .public_resume_metrics import metric

logger = logging.getLogger(__name__)


def private(view):
    @wraps(view)
    @never_cache
    def wrapped(request, *args, **kwargs):
        response = view(request, *args, **kwargs)
        response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
        response['Referrer-Policy'] = 'same-origin'
        return response
    return wrapped


def owner(request, create=False):
    token = request.session.get('public_resume_token')
    if not token and create:
        token = secrets.token_urlsafe(32)
        request.session['public_resume_token'] = token
    if not token:
        raise ValidationError('Your session expired. Keep a recovery copy and reopen the builder.')
    return salted_hmac('public-resume-session', token).hexdigest()


def ip_key(request):
    header = settings.PUBLIC_RESUME_CLIENT_IP_HEADER
    address = request.META.get(header, '') if header else request.META.get('REMOTE_ADDR', '')
    # No arbitrary X-Forwarded-For trust; rotate pseudonymous keys daily.
    return salted_hmac('public-resume-ip', timezone.now().date().isoformat() + ':' + address).hexdigest()


def gate():
    PublicBuilderGate.objects.select_for_update().get(pk=1)


def consume(key, limit, seconds):
    """Called under gate lock; DB-backed so limits apply across processes."""
    now = timezone.now()
    counter, _ = PublicBuilderCounter.objects.get_or_create(key=key, defaults={'expires_at': now + timedelta(seconds=seconds)})
    if counter.expires_at <= now:
        counter.count = 0
        counter.expires_at = now + timedelta(seconds=seconds)
    if counter.count >= limit:
        return False
    counter.count += 1
    counter.save(update_fields=['count', 'expires_at'])
    return True


def limited():
    response = JsonResponse({'detail': 'Please wait before trying again. The public builder has usage limits to keep it available.'}, status=429)
    response['Retry-After'] = '60'
    return response


def content_payload(request):
    data = payload(request)
    if set(data) != {'title', 'content'}:
        raise ValidationError('Send only title and content.')
    content = validate_content(data['content'])
    content['typography'] = dict(DEFAULT_TYPOGRAPHY)
    title = fields({'title': data['title']}, {'title': 120})['title'] or 'Untitled resume'
    return title, content


@require_GET
def landing(request):
    return render(request, 'website/resume_builder.html', {'canonical_url': settings.PUBLIC_SITE_URL + reverse('public_resume_landing')})


@private
@require_GET
def editor(request):
    owner(request, create=True)
    return render(request, 'product/resume_builder/editor.html', {'public': True, 'editor_base': 'website/public_app_base.html', 'initial': {
        'title': 'My resume', 'revision': 1, 'content': blank_content(),
        'typography_defaults': DEFAULT_TYPOGRAPHY, 'public': True,
    }})


@private
@require_GET
def session_token(request):
    from django.middleware.csrf import get_token
    return JsonResponse({'csrf': get_token(request)})


@private
@require_POST
def preview(request):
    try:
        session_hash = owner(request)
        with transaction.atomic():
            gate()
            if not consume('preview:' + ip_key(request), 120, 60):
                return limited()
            if consume('start:' + session_hash, 1, 86400):
                metric('editor_start')
        data = payload(request)
        if set(data) != {'content'}:
            raise ValidationError('Send only content.')
        content = validate_content(data['content'])
        content['typography'] = dict(DEFAULT_TYPOGRAPHY)
        return JsonResponse({'html': render_resume(content), 'content': content})
    except ValidationError as exc:
        return error(exc)


@private
@require_POST
def export(request):
    try:
        session_hash = owner(request)
        _, content = content_payload(request)
        if not content['contact']['name']:
            raise ValidationError('Enter your full name before exporting.')
    except ValidationError as exc:
        return error(exc)
    fingerprint = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
    with transaction.atomic():
        gate()
        now = timezone.now()
        expire_stalled_jobs(PublicResumePdfJob.objects.all())
        jobs = PublicResumePdfJob.objects.filter(session_hash=session_hash)
        job = jobs.filter(fingerprint=fingerprint, expires_at__gt=now, status__in=['queued', 'processing', 'ready']).first()
        created = job is None
        if created:
            from django_q.models import OrmQ
            if (jobs.filter(status__in=['queued', 'processing'], expires_at__gt=now).exists()
                or PublicResumePdfJob.objects.filter(status__in=['queued', 'processing'], expires_at__gt=now).count() >= settings.PUBLIC_RESUME_QUEUE_LIMIT
                or OrmQ.objects.count() >= settings.PUBLIC_RESUME_GLOBAL_QUEUE_LIMIT
                or ResumePdfJob.objects.filter(status__in=['queued', 'processing'], expires_at__gt=now).count() >= settings.PUBLIC_RESUME_GLOBAL_QUEUE_LIMIT):
                return limited()
            if not consume('export-session:' + session_hash, 3, 3600):
                return limited()
            if not consume('export-ip:' + ip_key(request), settings.PUBLIC_RESUME_IP_EXPORTS_PER_HOUR, 3600):
                return limited()
            job = PublicResumePdfJob.objects.create(session_hash=session_hash, fingerprint=fingerprint,
                content=content, expires_at=now + timedelta(minutes=30))
            metric('pdf_requested')
    if created:
        try:
            enqueue_background_job('apps.product.resume_pdf_jobs.generate_resume_pdf', job.pk, public=True)
        except Exception:
            logger.exception('Unable to enqueue public PDF job=%s', job.uuid)
            PublicResumePdfJob.objects.filter(pk=job.pk, status='queued').update(status='failed', content={}, error='Unable to queue PDF. Please try again.')
    return JsonResponse({'url': reverse('public_resume_pdf_detail', args=[job.uuid])})


def owned_job(request, job_uuid):
    try:
        session_hash = owner(request)
    except ValidationError:
        session_hash = ''
    job = get_object_or_404(PublicResumePdfJob, uuid=job_uuid, session_hash=session_hash)
    expire_stalled_jobs(PublicResumePdfJob.objects.filter(pk=job.pk))
    job.refresh_from_db()
    return job


@private
@require_GET
def pdf_detail(request, job_uuid):
    job = owned_job(request, job_uuid)
    return render(request, 'product/resume_builder/public_pdf.html', {
        'job': job, 'progress': progress_data(job), 'download': request.GET.get('download') == '1'})


@private
@require_GET
def pdf_status(request, job_uuid):
    return JsonResponse(progress_data(owned_job(request, job_uuid)))


@private
@require_GET
def pdf_file(request, job_uuid):
    job = owned_job(request, job_uuid)
    if job.expires_at <= timezone.now():
        return HttpResponse('PDF expired. Return to your open editor and export again.', status=410)
    if job.status != 'ready' or not job.file:
        return HttpResponse('PDF is not ready.', status=409)
    try:
        stream = job.file.open('rb')
    except FileNotFoundError:
        return HttpResponse('PDF is no longer available.', status=410)
    download = request.GET.get('download') == '1'
    if download:
        with transaction.atomic():
            gate()
            if consume('download:' + str(job.uuid), 1, 3600):
                metric('pdf_download')
    response = FileResponse(stream, content_type='application/pdf', filename='resume.pdf', as_attachment=download)
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@private
@require_POST
def transfer(request):
    try:
        session_hash = owner(request)
        title, content = content_payload(request)
    except ValidationError as exc:
        return error(exc)
    with transaction.atomic():
        gate()
        if not consume('transfer:' + ip_key(request), 20, 3600):
            return limited()
        pending = PublicResumeTransfer.objects.create(session_hash=session_hash, title=title, content=content,
            expires_at=timezone.now() + timedelta(hours=1))
    return JsonResponse({'url': reverse('public_resume_claim', args=[pending.uuid])})


@private
@login_required
@require_GET
def claim(request, transfer_uuid):
    try:
        session_hash = owner(request)
    except ValidationError:
        session_hash = ''
    pending = get_object_or_404(PublicResumeTransfer, uuid=transfer_uuid, session_hash=session_hash)
    return render(request, 'product/resume_builder/claim.html', {'pending': pending, 'expired': pending.expires_at <= timezone.now()})


@private
@login_required
@require_POST
def claim_save(request, transfer_uuid):
    try:
        session_hash = owner(request)
    except ValidationError:
        return HttpResponse('Session expired. Return to your original editor or recovery file.', status=410)
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        pending = get_object_or_404(PublicResumeTransfer.objects.select_for_update(), uuid=transfer_uuid, session_hash=session_hash)
        if pending.expires_at <= timezone.now():
            return HttpResponse('Transfer expired. Your original editor is still available. Start the transfer again there.', status=410)
        if pending.claimed:
            if pending.draft and pending.draft.user_id == request.user.pk:
                return redirect('resume_builder_edit', draft_uuid=pending.draft.uuid)
            return HttpResponse('This transfer was already used.', status=409)
        if ResumeDraft.objects.filter(user=request.user).count() >= 20:
            return HttpResponse('You have 20 drafts. Delete an unused draft, then retry. Your original editor remains open.', status=409)
        draft = ResumeDraft.objects.create(user=request.user, title=pending.title, content=validate_content(pending.content))
        pending.draft = draft
        pending.claimed = True
        pending.content = {}
        pending.save(update_fields=['draft', 'claimed', 'content'])
        metric('resume_saved')
    return redirect('resume_builder_edit', draft_uuid=draft.uuid)


class FreeSignupForm(UserCreationForm):
    email = forms.EmailField()
    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ('username', 'email')

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account already exists for this email. Please sign in.')
        return email


@private
@require_http_methods(['GET', 'POST'])
def signup(request):
    # Only an internal, same-session handoff is accepted as a destination.
    next_url = reverse('resume_builder_list')
    transfer_id = request.GET.get('transfer', '')
    if not transfer_id:
        from django.urls import resolve, Resolver404
        try:
            match = resolve(request.GET.get('next', ''))
            if match.url_name == 'public_resume_claim':
                transfer_id = match.kwargs['transfer_uuid']
        except Resolver404:
            pass
    pending = None
    if transfer_id:
        try:
            pending = PublicResumeTransfer.objects.filter(uuid=transfer_id, session_hash=owner(request), expires_at__gt=timezone.now()).first()
        except (ValidationError, ValueError):
            pass
    if pending:
        next_url = reverse('public_resume_claim', args=[pending.uuid])
    if request.user.is_authenticated:
        return redirect(next_url)
    form = FreeSignupForm(request.POST or None)
    if request.method == 'POST':
        with transaction.atomic():
            gate()
            if not consume('signup:' + ip_key(request), 5, 3600):
                return limited()
            if form.is_valid():
                # Gate serializes public registrations including case-insensitive email checks.
                user = form.save()
                EarlyAccessUser.objects.update_or_create(email=form.cleaned_data['email'], defaults={
                    'user': user, 'is_beta_active': True, 'signup_completed_at': timezone.now()})
                UserFeatureFlags.objects.create(user=user, can_access_coding_platform=True)
                metric('signup')
                login(request, user)
                return redirect(next_url)
    return render(request, 'product/auth/free_signup.html', {'form': form, 'next_url': next_url})
