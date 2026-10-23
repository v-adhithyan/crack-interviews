import json
from datetime import timedelta
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import PublicResumePdfJob, PublicResumeTransfer, PublicBuilderCounter, ResumeDraft
from .resume_builder import blank_content, DEFAULT_TYPOGRAPHY
from .resume_pdf_jobs import generate_resume_pdf, cleanup_expired_pdfs


class PublicResumeTests(TestCase):
    def setUp(self):
        self.client.get(reverse('public_resume_editor'))
        self.content = blank_content()
        self.content['contact']['name'] = 'Private Candidate'
        self.content['summary'] = '<script>alert(1)</script>'
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        field = PublicResumePdfJob._meta.get_field('file')
        old = field.storage
        field.storage = FileSystemStorage(location=self.directory.name)
        self.addCleanup(setattr, field, 'storage', old)

    def post(self, name, data=None, client=None):
        return (client or self.client).post(reverse(name), data=json.dumps(data if data is not None else {'title': 'My resume', 'content': self.content}), content_type='application/json')

    def export(self):
        with patch('apps.product.public_resume_views.enqueue_background_job'):
            response = self.post('public_resume_export')
        self.assertEqual(response.status_code, 200, response.content)
        return PublicResumePdfJob.objects.get(uuid=response.json()['url'].strip('/').split('/')[-1])

    def transfer(self):
        response = self.post('public_resume_transfer')
        self.assertEqual(response.status_code, 200)
        return PublicResumeTransfer.objects.get(uuid=response.json()['url'].strip('/').split('/')[-1])

    def test_public_editor_and_discovery(self):
        page = self.client.get(reverse('public_resume_editor'))
        self.assertContains(page, 'No autosave')
        self.assertContains(page, '"public": true')
        self.assertNotContains(page, 'data-save=')
        self.assertIn('noindex', page['X-Robots-Tag'])
        landing = self.client.get(reverse('public_resume_landing') + '?tracking=example')
        self.assertContains(landing, 'https://www.hackerleap.com/resume-builder/')
        self.assertNotIn('X-Robots-Tag', landing)
        self.assertContains(self.client.get('/sitemap.xml'), '/resume-builder/</loc>')
        self.assertContains(self.client.get('/robots.txt'), 'Disallow: /resume-builder/pdf/')

    def test_preview_escapes_text_forces_defaults_and_does_not_save(self):
        self.content['typography']['font'] = 'garamond'
        response = self.post('public_resume_preview', {'content': self.content})
        self.assertEqual(response.status_code, 200)
        self.assertIn('&lt;script&gt;', response.json()['html'])
        self.assertEqual(response.json()['content']['typography'], DEFAULT_TYPOGRAPHY)
        self.assertEqual(ResumeDraft.objects.count(), 0)
        self.assertEqual(PublicResumeTransfer.objects.count(), 0)
        self.assertEqual(PublicResumePdfJob.objects.count(), 0)
        self.assertNotIn('Private Candidate', str(list(PublicBuilderCounter.objects.values())))

    def test_csrf_required_on_mutations_and_error_responses_private(self):
        client = Client(enforce_csrf_checks=True)
        client.get(reverse('public_resume_editor'))
        for action in ['public_resume_preview', 'public_resume_export', 'public_resume_transfer']:
            response = self.post(action, client=client)
            self.assertEqual(response.status_code, 403)
            self.assertIn('noindex', response['X-Robots-Tag'])
        self.assertEqual(client.post(reverse('public_signup'), {}).status_code, 403)

    def test_missing_session_invalid_payload_and_methods(self):
        self.assertEqual(self.post('public_resume_export', client=Client()).status_code, 400)
        self.assertEqual(self.post('public_resume_export', {'title': 'x', 'content': {}}).status_code, 400)
        self.assertEqual(self.client.get(reverse('public_resume_export')).status_code, 405)
        self.assertEqual(self.client.post(reverse('public_resume_export'), data='x'*100001, content_type='application/json').status_code, 400)

    @patch('apps.product.public_resume_views.enqueue_background_job')
    def test_export_deduplicates_and_does_not_render_in_request(self, enqueue):
        with patch('apps.product.resume_pdf_jobs.render_pdf') as renderer:
            first = self.post('public_resume_export')
            second = self.post('public_resume_export')
        self.assertEqual(first.json(), second.json())
        self.assertEqual(PublicResumePdfJob.objects.count(), 1)
        enqueue.assert_called_once()
        self.assertEqual(enqueue.call_args.kwargs, {'public': True})
        renderer.assert_not_called()
        self.content['summary'] = 'changed'
        self.assertEqual(self.post('public_resume_export').status_code, 429)

    def test_session_isolation_for_detail_status_and_files(self):
        job = self.export()
        stranger = Client()
        stranger.get(reverse('public_resume_editor'))
        for action in ['detail', 'status', 'file']:
            url = reverse('public_resume_pdf_' + action, args=[job.uuid])
            self.assertEqual(stranger.get(url).status_code, 404)
            self.assertIn('noindex', stranger.get(url)['X-Robots-Tag'])
        self.assertEqual(self.client.get(reverse('public_resume_pdf_detail', args=[job.uuid])).status_code, 200)

    @patch('apps.product.resume_pdf_jobs.render_pdf', return_value=b'%PDF-test')
    def test_worker_ready_file_expiry_and_cleanup(self, renderer):
        job = self.export()
        generate_resume_pdf(job.pk, public=True)
        generate_resume_pdf(job.pk, public=True)
        renderer.assert_called_once()
        job.refresh_from_db()
        self.assertEqual(job.content, {})
        self.assertEqual(job.status, 'ready')
        response = self.client.get(reverse('public_resume_pdf_file', args=[job.uuid]) + '?download=1')
        self.assertEqual(b''.join(response.streaming_content), b'%PDF-test')
        response.close()
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('no-store', response['Cache-Control'])
        name, storage = job.file.name, job.file.storage
        PublicResumePdfJob.objects.filter(pk=job.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.client.get(reverse('public_resume_pdf_file', args=[job.uuid])).status_code, 410)
        with self.captureOnCommitCallbacks(execute=True):
            cleanup_expired_pdfs()
        self.assertFalse(storage.exists(name))

    @patch('apps.product.resume_pdf_jobs.render_pdf', side_effect=RuntimeError('renderer unavailable'))
    def test_failed_worker_clears_content(self, renderer):
        job = self.export()
        generate_resume_pdf(job.pk, public=True)
        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        self.assertEqual(job.content, {})
        self.assertNotIn('renderer unavailable', job.error)

    @override_settings(PUBLIC_RESUME_QUEUE_LIMIT=0)
    def test_global_queue_limit(self):
        self.assertEqual(self.post('public_resume_export').status_code, 429)
        self.assertFalse(PublicResumePdfJob.objects.exists())

    @override_settings(PUBLIC_RESUME_IP_EXPORTS_PER_HOUR=1)
    def test_ip_limit_survives_new_session_and_spoofed_forwarding(self):
        self.export()
        other = Client(HTTP_X_FORWARDED_FOR='8.8.8.8')
        other.get(reverse('public_resume_editor'))
        self.assertEqual(self.post('public_resume_export', client=other).status_code, 429)

    def test_preview_rate_limit(self):
        from .public_resume_views import ip_key
        request = self.client.get(reverse('public_resume_editor')).wsgi_request
        PublicBuilderCounter.objects.create(key='preview:' + ip_key(request), count=120, expires_at=timezone.now()+timedelta(minutes=1))
        self.assertEqual(self.post('public_resume_preview', {'content': self.content}).status_code, 429)

    def test_transfer_signup_claim_idempotent_and_owner_bound(self):
        pending = self.transfer()
        claim = reverse('public_resume_claim', args=[pending.uuid])
        self.assertEqual(self.client.get(claim).status_code, 302)
        response = self.client.post(reverse('public_signup') + '?next=' + claim, {
            'username': 'newperson', 'email': 'person@example.com', 'password1': 'Good-Long!Passphrase52', 'password2': 'Good-Long!Passphrase52'})
        self.assertEqual(response.status_code, 302, response.content)
        self.assertEqual(response.url, claim)
        user = get_user_model().objects.get(username='newperson')
        self.assertTrue(user.early_access_invite.is_beta_active)
        self.assertTrue(user.feature_flags.can_access_coding_platform)
        self.assertEqual(ResumeDraft.objects.count(), 0)
        self.assertEqual(self.client.get(claim).status_code, 200)
        save = reverse('public_resume_claim_save', args=[pending.uuid])
        first = self.client.post(save)
        second = self.client.post(save)
        self.assertEqual(first.url, second.url)
        self.assertEqual(ResumeDraft.objects.count(), 1)
        draft = ResumeDraft.objects.get()
        self.assertEqual(draft.user, user)
        self.assertEqual(draft.content['contact']['name'], 'Private Candidate')
        pending.refresh_from_db()
        self.assertEqual(pending.content, {})
        other = Client()
        other.force_login(user)
        self.assertEqual(other.post(save).status_code, 410)

    def test_transfer_expired_and_cancelled(self):
        pending = self.transfer()
        user = get_user_model().objects.create_user('existing')
        self.client.force_login(user)
        PublicResumeTransfer.objects.filter(pk=pending.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        response = self.client.get(reverse('public_resume_claim', args=[pending.uuid]))
        self.assertContains(response, 'transfer expired')
        self.assertEqual(self.client.post(reverse('public_resume_claim_save', args=[pending.uuid])).status_code, 410)
        self.assertEqual(ResumeDraft.objects.count(), 0)

    def test_signup_rejects_weak_password_and_external_redirect(self):
        response = self.client.post(reverse('public_signup') + '?next=https://evil.test/', {'username': 'bad', 'email': 'bad@example.com', 'password1': '123', 'password2': '123'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username='bad').exists())

    def test_articles_are_idempotent_and_do_not_overwrite_cms(self):
        from apps.website.models import BlogPost
        call_command('publish_resume_guides', verbosity=0)
        post = BlogPost.objects.get(slug='resume-builder-comparison')
        self.assertIn('19 October 2026', post.content)
        post.content = 'Edited by owner'; post.save()
        call_command('publish_resume_guides', verbosity=0)
        post.refresh_from_db()
        self.assertEqual(post.content, 'Edited by owner')
