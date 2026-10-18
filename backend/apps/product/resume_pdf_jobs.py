"""Private, expiring PDF artifacts rendered outside web requests."""
import logging
from datetime import timedelta

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone

from .models import ResumePdfJob
from .resume_builder import render_pdf

logger = logging.getLogger(__name__)


def expire_stalled_jobs(queryset):
    now = timezone.now()
    queryset.filter(status='queued', created_at__lt=now - timedelta(minutes=5)).update(
        status='failed', content={}, error='PDF queue timed out. Please request a new export.')
    queryset.filter(status='processing', started_at__lt=now - timedelta(minutes=2)).update(
        status='failed', content={}, error='PDF generation timed out. Please request a new export.')


def generate_resume_pdf(job_id):
    # Only one delivery can claim this job; duplicate queue deliveries are harmless.
    now = timezone.now()
    claimed = ResumePdfJob.objects.filter(pk=job_id, status='queued',
        created_at__gte=now - timedelta(minutes=5), expires_at__gt=now).update(status='processing', started_at=now)
    if not claimed:
        return
    job = ResumePdfJob.objects.filter(pk=job_id).first()
    if job is None:
        return
    saved_name = None
    try:
        pdf = render_pdf(job.content)
        with transaction.atomic():
            current = ResumePdfJob.objects.select_for_update().filter(pk=job_id, status='processing', expires_at__gt=timezone.now()).first()
            if current is None:
                return
            current.file.save(f'{current.uuid}.pdf', ContentFile(pdf), save=False)
            saved_name = current.file.name
            current.status = ResumePdfJob.Status.READY
            current.content = {}
            current.save(update_fields=['file', 'status', 'content'])
    except Exception:
        logger.exception('Queued resume PDF generation failed (job %s)', job.uuid)
        if saved_name:
            job.file.storage.delete(saved_name)
        ResumePdfJob.objects.filter(pk=job_id, status='processing').update(
            status='failed', content={}, error='PDF generation failed. Please try again or shorten your resume.')


@receiver(post_delete, sender=ResumePdfJob)
def delete_pdf_artifact(sender, instance, **kwargs):
    if instance.file:
        name, storage = instance.file.name, instance.file.storage
        transaction.on_commit(lambda: storage.delete(name))


def cleanup_expired_pdfs():
    count = 0
    while True:
        ids = list(ResumePdfJob.objects.filter(expires_at__lte=timezone.now()).values_list('pk', flat=True)[:100])
        if not ids:
            return count
        ResumePdfJob.objects.filter(pk__in=ids).delete()
        count += len(ids)
