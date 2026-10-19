"""Private, expiring PDF artifacts rendered outside web requests."""
import logging
from time import monotonic
from datetime import timedelta

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone

from .models import ResumePdfJob, PublicResumePdfJob, PublicResumeTransfer, PublicBuilderCounter
from .resume_builder import render_pdf

logger = logging.getLogger(__name__)


def expire_stalled_jobs(queryset):
    now = timezone.now()
    queryset.filter(status='queued', created_at__lt=now - timedelta(minutes=5)).update(
        status='failed', content={}, error='PDF queue timed out. Please request a new export.')
    queryset.filter(status='processing', started_at__lt=now - timedelta(minutes=2)).update(
        status='failed', content={}, error='PDF generation timed out. Please request a new export.')


def generate_resume_pdf(job_id, public=False):
    model = PublicResumePdfJob if public else ResumePdfJob
    # Only one delivery can claim this job; duplicate queue deliveries are harmless.
    now = timezone.now()
    claimed = model.objects.filter(pk=job_id, status='queued',
        created_at__gte=now - timedelta(minutes=5), expires_at__gt=now).update(status='processing', started_at=now)
    if not claimed:
        return
    job = model.objects.filter(pk=job_id).first()
    if job is None:
        return
    saved_name = None
    stage = 'render'
    started = monotonic()
    logger.info('PDF job started job=%s draft=%s revision=%s', job.uuid, getattr(job, 'draft_id', None), job.revision)
    try:
        pdf = render_pdf(job.content)
        stage = 'store'
        logger.info('PDF resources public=%s queue_seconds=%.2f bytes=%d', public, (now - job.created_at).total_seconds(), len(pdf))
        with transaction.atomic():
            current = model.objects.select_for_update().filter(pk=job_id, status='processing', expires_at__gt=timezone.now()).first()
            if current is None:
                logger.warning('PDF job discarded before storage job=%s (deleted, expired or no longer processing)', job.uuid)
                return
            current.file.save(f'{current.uuid}.pdf', ContentFile(pdf), save=False)
            saved_name = current.file.name
            current.status = 'ready'
            current.content = {}
            stage = 'persist_ready'
            current.save(update_fields=['file', 'status', 'content'])
        if public:
            from .public_resume_metrics import metric
            metric('pdf_ready')
            metric('pdf_bytes', len(pdf))
            metric('pdf_queue_ms', max(0, int((now - job.created_at).total_seconds() * 1000)))
            metric('pdf_render_ms', int((monotonic() - started) * 1000))
        logger.info('PDF job ready job=%s bytes=%d elapsed_seconds=%.2f', job.uuid, len(pdf), monotonic() - started)
    except Exception:
        logger.exception('Queued resume PDF generation failed job=%s draft=%s revision=%s stage=%s elapsed_seconds=%.2f', job.uuid, getattr(job, 'draft_id', None), job.revision, stage, monotonic() - started)
        if saved_name:
            try:
                job.file.storage.delete(saved_name)
            except Exception:
                logger.exception('PDF artifact cleanup failed job=%s', job.uuid)
        model.objects.filter(pk=job_id, status='processing').update(
            status='failed', content={}, error='PDF generation failed. Please try again or shorten your resume.')
        if public:
            from .public_resume_metrics import metric
            metric('pdf_failed')


@receiver(post_delete, sender=PublicResumePdfJob)
@receiver(post_delete, sender=ResumePdfJob)
def delete_pdf_artifact(sender, instance, **kwargs):
    if instance.file:
        name, storage = instance.file.name, instance.file.storage
        transaction.on_commit(lambda: storage.delete(name))


def cleanup_expired_pdfs():
    PublicResumeTransfer.objects.filter(expires_at__lte=timezone.now()).delete()
    PublicBuilderCounter.objects.filter(expires_at__lte=timezone.now()).delete()
    PublicResumePdfJob.objects.filter(expires_at__lte=timezone.now()).delete()
    count = 0
    while True:
        ids = list(ResumePdfJob.objects.filter(expires_at__lte=timezone.now()).values_list('pk', flat=True)[:100])
        if not ids:
            return count
        ResumePdfJob.objects.filter(pk__in=ids).delete()
        count += len(ids)
