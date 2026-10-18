from datetime import timedelta
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.website.models import EarlyAccessUser
from .models import ResumeDraft, ResumePdfJob
from .resume_builder import blank_content
from .resume_pdf_jobs import generate_resume_pdf


class ResumePdfJobsTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        override = override_settings(MEDIA_ROOT=self.directory.name)
        override.enable()
        self.addCleanup(override.disable)
        self.user = get_user_model().objects.create_user('pdf-owner')
        EarlyAccessUser.objects.create(user=self.user, email='pdf@example.test', is_beta_active=True)
        self.client.force_login(self.user)
        self.content = blank_content()
        self.content['contact']['name'] = 'Engineer'
        self.draft = ResumeDraft.objects.create(user=self.user, content=self.content)
        self.export_url = reverse('resume_builder_export', kwargs={'draft_uuid': self.draft.uuid})

    def job(self, **changes):
        return ResumePdfJob.objects.create(draft=self.draft, revision=1, content=self.content,
            expires_at=timezone.now() + timedelta(hours=1), **changes)

    def url(self, action, job):
        return reverse('resume_pdf_' + action, kwargs={'job_uuid': job.uuid})

    @patch('apps.product.resume_pdf_views.enqueue_background_job')
    @patch('apps.product.resume_pdf_jobs.render_pdf')
    def test_export_only_enqueues_and_deduplicates_preview_and_download(self, renderer, enqueue):
        response = self.client.post(self.export_url, {'revision': 1})
        self.assertEqual(response.status_code, 302)
        job = ResumePdfJob.objects.get()
        self.assertEqual(response.url, self.url('detail', job))
        self.assertEqual(job.content, self.content)
        enqueue.assert_called_once_with('apps.product.resume_pdf_jobs.generate_resume_pdf', job.pk)
        renderer.assert_not_called()
        response = self.client.post(self.export_url, {'revision': 1, 'download': '1'})
        self.assertEqual(response.url, self.url('detail', job) + '?download=1')
        self.assertEqual(ResumePdfJob.objects.count(), 1)
        self.assertEqual(enqueue.call_count, 1)
        self.assertEqual(self.client.post(self.export_url, {'revision': 2}).status_code, 409)

    @patch('apps.product.resume_pdf_jobs.render_pdf', return_value=b'%PDF-example')
    def test_worker_snapshot_ready_download_headers_and_duplicate_delivery(self, renderer):
        job = self.job()
        self.draft.content = {**self.content, 'summary': 'Later edit'}
        self.draft.save()
        generate_resume_pdf(job.pk)
        generate_resume_pdf(job.pk)
        renderer.assert_called_once_with(self.content)
        job.refresh_from_db()
        self.assertEqual(job.status, 'ready')
        self.assertEqual(job.content, {})
        self.assertEqual(self.client.get(self.url('status', job)).json()['status'], 'ready')
        for suffix, disposition in [('', 'inline'), ('?download=1', 'attachment')]:
            response = self.client.get(self.url('file', job) + suffix)
            self.assertEqual(response.status_code, 200)
            self.assertIn(disposition, response['Content-Disposition'])
            self.assertIn('private', response['Cache-Control'])
            self.assertEqual(b''.join(response.streaming_content), b'%PDF-example')
            response.close()
        self.assertContains(self.client.get(self.url('detail', job)), 'Saved revision 1')

    @patch('apps.product.resume_pdf_views.enqueue_background_job', side_effect=RuntimeError('broker down'))
    def test_enqueue_failure_is_visible_and_can_retry(self, enqueue):
        with self.assertLogs('apps.product.resume_pdf_views', level='ERROR'):
            self.client.post(self.export_url, {'revision': 1})
        job = ResumePdfJob.objects.get()
        self.assertEqual(job.status, 'failed')
        self.assertEqual(job.content, {})
        self.assertNotIn('broker down', job.error)
        with patch('apps.product.resume_pdf_views.enqueue_background_job'):
            self.assertEqual(self.client.post(self.export_url, {'revision': 1}).status_code, 302)
        self.assertEqual(ResumePdfJob.objects.count(), 2)

    @patch('apps.product.resume_pdf_jobs.render_pdf', side_effect=RuntimeError('private renderer details'))
    def test_worker_failure_is_safe(self, renderer):
        job = self.job()
        with self.assertLogs('apps.product.resume_pdf_jobs', level='ERROR'):
            generate_resume_pdf(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        self.assertEqual(job.content, {})
        self.assertNotIn('private renderer details', job.error)
        self.assertEqual(self.client.get(self.url('file', job)).status_code, 409)

    def test_owner_only_csrf_and_methods(self):
        job = self.job()
        self.assertEqual(self.client.get(self.export_url).status_code, 405)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(self.export_url, {'revision': 1}).status_code, 403)
        other = get_user_model().objects.create_user('staff', is_staff=True)
        self.client.force_login(other)
        for action in ['detail', 'status', 'file']:
            self.assertEqual(self.client.get(self.url(action, job)).status_code, 404)
        self.assertEqual(self.client.post(self.export_url, {'revision': 1}).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(self.url('file', job)).status_code, 302)

    @patch('apps.product.resume_pdf_jobs.render_pdf', return_value=b'%PDF-example')
    def test_expiry_cleanup_and_draft_deletion_remove_files(self, renderer):
        job = self.job()
        generate_resume_pdf(job.pk)
        job.refresh_from_db()
        storage, name = job.file.storage, job.file.name
        ResumePdfJob.objects.filter(pk=job.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.get(self.url('file', job)).status_code, 410)
        self.assertEqual(self.client.get(self.url('status', job)).json()['status'], 'expired')
        with self.captureOnCommitCallbacks(execute=True):
            call_command('cleanup_resume_pdfs')
        self.assertFalse(storage.exists(name))
        job = self.job()
        generate_resume_pdf(job.pk)
        job.refresh_from_db()
        name = job.file.name
        with self.captureOnCommitCallbacks(execute=True):
            self.draft.delete()
        self.assertFalse(storage.exists(name))

    @patch('apps.product.resume_pdf_views.enqueue_background_job')
    def test_stalled_jobs_and_per_user_capacity(self, enqueue):
        job = self.job()
        second = ResumeDraft.objects.create(user=self.user, content=self.content)
        url = reverse('resume_builder_export', kwargs={'draft_uuid': second.uuid})
        self.assertEqual(self.client.post(url, {'revision': 1}).status_code, 429)
        ResumePdfJob.objects.filter(pk=job.pk).update(created_at=timezone.now() - timedelta(minutes=6))
        self.assertEqual(self.client.get(self.url('status', job)).json()['status'], 'failed')
        self.assertEqual(self.client.post(url, {'revision': 1}).status_code, 302)
        pending = ResumePdfJob.objects.get(draft=second)
        ResumePdfJob.objects.filter(pk=pending.pk).update(status='processing', started_at=timezone.now() - timedelta(minutes=3))
        self.assertEqual(self.client.get(self.url('status', pending)).json()['status'], 'failed')
        for _ in range(9):
            self.job(status='failed')
        self.assertEqual(self.client.post(self.export_url, {'revision': 1}).status_code, 429)

    def test_deleted_draft_during_render_does_not_leave_artifact(self):
        job = self.job()
        def rendering(content):
            self.draft.delete()
            return b'%PDF-example'
        with patch('apps.product.resume_pdf_jobs.render_pdf', side_effect=rendering):
            generate_resume_pdf(job.pk)
        self.assertFalse(ResumePdfJob.objects.exists())
        from pathlib import Path
        self.assertFalse(list(Path(self.directory.name).rglob('*.pdf')))

    @patch('apps.product.resume_pdf_jobs.render_pdf', return_value=b'%PDF-example')
    @patch('apps.product.resume_pdf_views.enqueue_background_job')
    def test_missing_artifact_allows_new_export(self, enqueue, renderer):
        job = self.job()
        generate_resume_pdf(job.pk)
        job.refresh_from_db()
        job.file.storage.delete(job.file.name)
        self.assertEqual(self.client.get(self.url('file', job)).status_code, 410)
        self.assertEqual(self.client.post(self.export_url, {'revision': 1}).status_code, 302)
        enqueue.assert_called_once()
        self.assertEqual(ResumePdfJob.objects.count(), 2)

    def test_pdf_progress_matches_real_job_stages(self):
        job = self.job()
        for state, percent in [('queued', 15), ('processing', 60), ('ready', 100), ('failed', None)]:
            ResumePdfJob.objects.filter(pk=job.pk).update(status=state, started_at=timezone.now())
            data = self.client.get(self.url('status', job)).json()
            self.assertEqual(data['status'], state)
            self.assertEqual(data['progress'], percent)
            self.assertTrue(data['label'])
            self.assertTrue(data['stage'])
        ResumePdfJob.objects.filter(pk=job.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        data = self.client.get(self.url('status', job)).json()
        self.assertEqual(data['status'], 'expired')
        self.assertIsNone(data['progress'])

    def test_preview_and_download_show_analysis_style_progress(self):
        job = self.job()
        for suffix in ['', '?download=1']:
            response = self.client.get(self.url('detail', job) + suffix)
            self.assertContains(response, 'class="analysis-progress-card"')
            self.assertContains(response, 'role="progressbar"')
            self.assertContains(response, 'aria-valuenow="15"')
            self.assertContains(response, 'Progress reflects completed stages')
