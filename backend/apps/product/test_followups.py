import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.website.models import EarlyAccessUser
from .models import Resume, ResumeAnalysis, AnalysisFollowup
from .followups import clean_questions, parse_result, run_followup


@override_settings(HACKERLEAP_AI_MODE='manual')
class FollowupTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('followup', password='test')
        EarlyAccessUser.objects.create(user=self.user, email='followup@example.test', is_beta_active=True)
        self.client.force_login(self.user)
        self.resume = Resume.objects.create(user=self.user, original_filename='resume.pdf', size=1, parsed_text='NEW resume')
        self.analysis = ResumeAnalysis.objects.create(user=self.user, resume=self.resume,
            job_description='Python job', resume_text='ORIGINAL resume', status='result_added',
            ai_response_json={'status': 'success', 'suggestions': ['Explain impact']})
        self.url = reverse('analysis_followup_create', args=[self.analysis.uuid])

    def create(self, **extra):
        response = self.client.post(self.url, {'questions': ['How should I position my experience?'], **extra})
        self.assertEqual(response.status_code, 302)
        return AnalysisFollowup.objects.latest('id')

    def answer(self, job, **extra):
        return json.dumps({'answers': [{'question_id': i, 'answer': 'Example answer'} for i, _ in enumerate(job.questions, 1)],
                          'cover_letter': 'Dear hiring team' if job.include_cover_letter else '', **extra})

    def test_manual_snapshot_and_duplicate_requests(self):
        job = self.create(cover_letter='on')
        self.assertEqual(job.status, 'manual')
        self.assertIn('ORIGINAL resume', job.prompt)
        self.assertNotIn('NEW resume', job.prompt)
        self.assertIn('Python job', job.prompt)
        self.assertIn('Explain impact', job.prompt)
        self.assertEqual(self.create(cover_letter='on').pk, job.pk)
        self.assertEqual(AnalysisFollowup.objects.count(), 1)
        self.assertContains(self.client.get(reverse('analysis_followup_detail', args=[job.uuid])), 'Copy prompt')

    def test_question_limits(self):
        for questions in ([], [''] , ['q']*11, ['x'*1001], ['bad\x00']):
            with self.subTest(questions=questions), self.assertRaises(ValidationError):
                clean_questions(questions)
        self.assertEqual(len(clean_questions(['question']*10)), 10)
        self.assertContains(self.client.post(self.url, {'questions': ['q']*11}), 'Ask between 1 and 10')
        self.assertEqual(AnalysisFollowup.objects.count(), 0)

    def test_answers_cover_letter_copy_and_escape(self):
        job = self.create(cover_letter='on', questions=['First?', 'Second?'])
        url = reverse('analysis_followup_detail', args=[job.uuid])
        response = self.client.post(url, {'response_json': self.answer(job, cover_letter='<script>danger</script>')})
        self.assertEqual(response.status_code, 302)
        page = self.client.get(url)
        self.assertContains(page, 'Copy answer', count=2)
        self.assertContains(page, 'Copy cover letter')
        self.assertContains(page, '&lt;script&gt;danger&lt;/script&gt;')
        self.assertNotContains(page, '<script>danger</script>')
        self.assertEqual(self.client.post(url, {'response_json': self.answer(job)}).status_code, 409)

    def test_invalid_responses(self):
        job = self.create(cover_letter='on')
        for raw in ('[]', '{}', 'not json', 'x'*100001,
                    self.answer(job, answers=[]), self.answer(job, cover_letter=''),
                    self.answer(job, answers=[{'question_id': True, 'answer': 'x'}]),
                    self.answer(job, answers=[{'question_id': 2, 'answer': 'x'}])):
            with self.subTest(raw=raw[:80]), self.assertRaises(ValidationError):
                parse_result(raw, job)
        url = reverse('analysis_followup_detail', args=[job.uuid])
        self.assertContains(self.client.post(url, {'response_json': '{}'}), 'must contain answers')
        job.refresh_from_db()
        self.assertEqual(job.status, 'manual')

    def test_owner_auth_csrf_and_completed_analysis(self):
        job = self.create()
        detail = reverse('analysis_followup_detail', args=[job.uuid])
        status = reverse('analysis_followup_status', args=[job.uuid])
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.user)
        self.assertEqual(csrf.post(self.url, {'questions': ['q']}).status_code, 403)
        self.assertEqual(csrf.post(detail, {'response_json': '{}'}).status_code, 403)
        other = get_user_model().objects.create_user('other', is_staff=True)
        self.client.force_login(other)
        for url in (self.url, detail, status):
            self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(detail, {'response_json': self.answer(job)}).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.force_login(self.user)
        self.analysis.status='queued'; self.analysis.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)

    @patch('apps.product.followup_views.enqueue_background_job')
    @patch('apps.product.followup_views.reserve_resume_analysis_ai_quota', return_value=True)
    @patch('apps.product.followup_views.get_effective_resume_analysis_mode', return_value='chatgpt')
    def test_queued_duplicate_submission_consumes_quota_once(self, mode, quota, enqueue):
        job = self.create()
        self.assertEqual(job.status, 'queued')
        self.create()
        quota.assert_called_once()
        enqueue.assert_called_once_with('apps.product.followups.run_followup', job.pk)
        url = reverse('analysis_followup_detail', args=[job.uuid])
        self.assertEqual(self.client.post(url, {'response_json': self.answer(job)}).status_code, 409)
        AnalysisFollowup.objects.filter(pk=job.pk).update(updated_at=timezone.now()-timedelta(minutes=6))
        self.assertEqual(self.client.get(reverse('analysis_followup_status', args=[job.uuid])).json()['status'], 'failed')
        self.assertEqual(self.client.post(url, {'response_json': self.answer(job)}).status_code, 302)

    @patch('apps.product.followup_views.reserve_resume_analysis_ai_quota', return_value=False)
    @patch('apps.product.followup_views.get_effective_resume_analysis_mode', return_value='chatgpt')
    def test_quota_exhaustion_falls_back_to_manual(self, mode, quota):
        self.assertEqual(self.create().status, 'manual')

    @override_settings(OPENAI_API_KEY='test', OPENAI_MODEL='test-model')
    @patch('openai.OpenAI')
    def test_worker_validates_and_does_not_repeat(self, client):
        job = self.create()
        AnalysisFollowup.objects.filter(pk=job.pk).update(status='queued')
        client.return_value.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.answer(job)))])
        run_followup(job.pk); run_followup(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, 'ready')
        client.return_value.chat.completions.create.assert_called_once()
        self.assertIn('ORIGINAL resume', client.return_value.chat.completions.create.call_args.kwargs['messages'][1]['content'])

    @override_settings(OPENAI_API_KEY='test')
    @patch('openai.OpenAI')
    def test_worker_failure_does_not_expose_provider_error(self, client):
        job = self.create()
        AnalysisFollowup.objects.filter(pk=job.pk).update(status='queued')
        client.return_value.chat.completions.create.side_effect = RuntimeError('secret provider detail')
        run_followup(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        page=self.client.get(reverse('analysis_followup_detail', args=[job.uuid]))
        self.assertNotContains(page, 'secret provider detail')
        self.assertContains(page, 'Copy prompt')

    def test_daily_batch_limit(self):
        for i in range(20):
            AnalysisFollowup.objects.create(analysis=self.analysis, request_key=str(i), questions=['q'], prompt='prompt')
        self.assertContains(self.client.post(self.url, {'questions': ['new']}), 'up to 20 follow-up batches')
        self.assertEqual(AnalysisFollowup.objects.count(), 20)
