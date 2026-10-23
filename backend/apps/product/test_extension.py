import copy
import json
from uuid import uuid4
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.website.models import EarlyAccessUser
from .models import Resume, ResumeDraft, ResumeAnalysis
from .resume_builder import blank_content
from .extension_views import selection


@override_settings(HACKERLEAP_AI_MODE='manual')
class ExtensionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('extension', password='test')
        EarlyAccessUser.objects.create(user=self.user, email='extension@example.test', is_beta_active=True)
        self.client.force_login(self.user)
        content = blank_content(); content['contact']['name'] = 'Test Engineer'
        content['summary'] = 'Builds Python services.'
        content['projects'] = [dict(name='My Product', website='', start_year='2023', end_year='Present', bullets='Built search')]
        self.draft = ResumeDraft.objects.create(user=self.user, title='Python Resume', content=content)
        self.list_url = reverse('extension_resumes'); self.submit_url = reverse('extension_submit')
        self.body = {'selection': self.client.get(self.list_url).json()['resumes'][0]['selection'],
            'request_id': str(uuid4()), 'job': {'source': 'ashby', 'title': 'Engineer', 'company': 'Example',
            'url': 'https://jobs.ashbyhq.com/Example/' + str(uuid4()), 'description': 'Build Python services.'}}

    def submit(self, body=None, client=None):
        return (client or self.client).post(self.submit_url, body or self.body, content_type='application/json')

    def test_linkedin_submission(self):
        self.body['job']['source'] = 'linkedin'
        self.body['job']['url'] = 'https://www.linkedin.com/jobs/view/1234567890/'
        response = self.submit()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ResumeAnalysis.objects.get().status, 'prompt_ready')

    def test_personio_and_lever_submission(self):
        for source, url in [
            ('personio', 'https://example.jobs.personio.de/job/12345?language=en'),
            ('lever', 'https://jobs.eu.lever.co/example/' + str(uuid4())),
        ]:
            with self.subTest(source=source):
                body = copy.deepcopy(self.body)
                body['request_id'] = str(uuid4())
                body['job'].update(source=source, url=url)
                response = self.submit(body)
                self.assertEqual(response.status_code, 201)
                analysis = ResumeAnalysis.objects.get(submission_key=body['request_id'])
                self.assertEqual(analysis.status, 'prompt_ready')
                self.assertIn('Build Python services.', analysis.job_description)
                self.assertEqual(analysis.builder_snapshot['content'], self.draft.content)

    def test_private_metadata_only_and_no_cache(self):
        response = self.client.get(self.list_url)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertContains(response, 'Python Resume')
        self.assertNotContains(response, 'Builds Python services')
        self.assertNotContains(response, 'Built search')
        self.assertIn('csrf_token', response.json())

    def test_draft_only_analysis_without_replacing_default_resume(self):
        response = self.submit()
        self.assertEqual(response.status_code, 201)
        analysis = ResumeAnalysis.objects.get()
        self.assertIsNone(analysis.resume_id)
        self.assertEqual(Resume.objects.count(), 0)
        self.assertEqual(analysis.builder_snapshot['content'], self.draft.content)
        self.assertIn('Built search', analysis.resume_text)
        self.assertIn('Job title: Engineer', analysis.job_description)
        self.assertIn('Company: Example', analysis.job_description)
        self.assertEqual(analysis.status, 'prompt_ready')
        self.assertContains(self.client.get(response.json()['url']), 'Save analysis result')
        self.assertIn('Python Resume', str(analysis))
        self.draft.content['summary'] = 'Changed'; self.draft.save()
        analysis.refresh_from_db()
        self.assertIn('Builds Python services', analysis.resume_text)

    def test_existing_uploaded_resume_is_unchanged(self):
        resume = Resume.objects.create(user=self.user, original_filename='old.pdf', size=1, parsed_text='Old resume')
        self.submit()
        resume.refresh_from_db()
        self.assertEqual(resume.parsed_text, 'Old resume')
        self.assertEqual(resume.builder_snapshot, {})

    def test_uploaded_resume_selection_and_stale_detection(self):
        resume = Resume.objects.create(user=self.user, original_filename='old.pdf', size=1, parsed_text='Uploaded text')
        row = self.client.get(self.list_url).json()['resumes'][-1]
        self.body['selection'] = row['selection']
        self.assertEqual(self.submit().status_code, 201)
        self.assertEqual(ResumeAnalysis.objects.get().resume_id, resume.pk)
        self.body['request_id'] = str(uuid4()); resume.parsed_text='New text'; resume.save()
        self.assertEqual(self.submit().status_code, 409)

    def test_ownership_auth_and_csrf(self):
        other = get_user_model().objects.create_user('other', is_staff=True)
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.list_url).json()['resumes'], [])
        self.assertEqual(self.submit().status_code, 409)
        self.client.logout()
        self.assertEqual(self.client.get(self.list_url).status_code, 401)
        self.assertEqual(self.submit().status_code, 401)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.user)
        self.assertEqual(self.submit(client=csrf).status_code, 403)
        bootstrap = csrf.get(self.list_url).json()
        response=csrf.post(self.submit_url, self.body, content_type='application/json', HTTP_X_CSRFTOKEN=bootstrap['csrf_token'])
        self.assertEqual(response.status_code, 201)

    def test_changed_deleted_and_forged_selections(self):
        self.draft.revision=2; self.draft.save()
        self.assertEqual(self.submit().status_code, 409)
        self.draft.delete()
        self.assertEqual(self.submit().status_code, 409)
        self.body['selection'] += 'tampered'
        self.assertEqual(self.submit().status_code, 400)

    def test_invalid_job_and_empty_name(self):
        for value in ['', 'x'*12001, None]:
            body=copy.deepcopy(self.body); body['job']['description']=value
            self.assertEqual(self.submit(body).status_code, 400)
        body=copy.deepcopy(self.body); body['job']['url']='javascript:alert(1)'
        self.assertEqual(self.submit(body).status_code, 400)
        self.draft.content['contact']['name']=''; self.draft.save()
        self.assertEqual(self.submit().status_code, 400)
        self.assertEqual(ResumeAnalysis.objects.count(), 0)

    @patch('apps.product.extension_views.enqueue_background_job', return_value='task-id')
    @patch('apps.product.extension_views.reserve_resume_analysis_ai_quota', return_value=True)
    @patch('apps.product.extension_views.get_effective_resume_analysis_mode', return_value='chatgpt')
    def test_queue_idempotency_and_payload_conflict(self, mode, quota, enqueue):
        first=self.submit(); second=self.submit()
        self.assertEqual(first.status_code, 201); self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(first.json()['status'], 'queued')
        analysis=ResumeAnalysis.objects.get()
        enqueue.assert_called_once_with('apps.product.tasks.run_resume_analysis', analysis.pk)
        quota.assert_called_once()
        self.body['job']['description']='A different job'
        self.assertEqual(self.submit().status_code, 409)

    @patch('apps.product.extension_views.enqueue_background_job', side_effect=RuntimeError('private provider message'))
    @patch('apps.product.extension_views.reserve_resume_analysis_ai_quota', return_value=True)
    @patch('apps.product.extension_views.get_effective_resume_analysis_mode', return_value='chatgpt')
    def test_enqueue_failure_is_safe(self, mode, quota, enqueue):
        response=self.submit()
        self.assertEqual(response.json()['status'], 'failed')
        self.assertNotContains(response, 'private provider message', status_code=201)

    @patch('apps.product.extension_views.reserve_resume_analysis_ai_quota', return_value=False)
    @patch('apps.product.extension_views.get_effective_resume_analysis_mode', return_value='chatgpt')
    def test_quota_exhaustion_uses_manual(self, mode, quota):
        self.assertEqual(self.submit().json()['status'], 'prompt_ready')

    def test_manual_submissions_use_hackerleap_rules_without_extension_cap(self):
        for _ in range(20):
            ResumeAnalysis.objects.create(user=self.user, job_description='job',resume_text='resume',generated_prompt='prompt',submission_key=uuid4())
        response = self.submit()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['status'], 'prompt_ready')

    @patch('apps.product.extension_views.enqueue_background_job', return_value='task')
    @patch('apps.product.extension_views.reserve_resume_analysis_ai_quota', return_value=True)
    @patch('apps.product.extension_views.get_effective_resume_analysis_mode', return_value='chatgpt')
    def test_more_than_twenty_submissions_still_obey_server_ai_allowance(self, mode, quota, enqueue):
        for _ in range(20):
            ResumeAnalysis.objects.create(user=self.user, job_description='job', resume_text='resume', generated_prompt='prompt', submission_key=uuid4())
        response = self.submit()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['status'], 'queued')
        quota.assert_called_once_with(self.user)
        enqueue.assert_called_once()

    @patch('apps.product.extension_views.enqueue_background_job')
    @patch('apps.product.extension_views.reserve_resume_analysis_ai_quota', return_value=False)
    @patch('apps.product.extension_views.get_effective_resume_analysis_mode', return_value='chatgpt')
    def test_more_than_twenty_submissions_with_exhausted_ai_use_manual(self, mode, quota, enqueue):
        for _ in range(20):
            ResumeAnalysis.objects.create(user=self.user, job_description='job', resume_text='resume', generated_prompt='prompt', submission_key=uuid4())
        response = self.submit()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['status'], 'prompt_ready')
        quota.assert_called_once_with(self.user)
        enqueue.assert_not_called()
