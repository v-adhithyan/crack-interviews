"""Product-scale track integration and compatibility with existing interview modes."""
import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.website.models import EarlyAccessUser
from .forms import MockInterviewStartForm, SYSTEM_DESIGN_TOPICS
from .interview_coaching import coaching_prompt
from .interview_tracks import PRODUCT_SCALE_TOPICS, PRODUCT_SCALE_FEEDBACK_INSTRUCTIONS
from .models import MockInterviewSession
from .services import build_mock_interview_instructions, create_mock_interview_realtime_token, generate_mock_interview_feedback


class ProductScaleInterviewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('product-scale', password='test')
        EarlyAccessUser.objects.create(user=self.user, email='scale@example.test', is_beta_active=True)
        self.client.force_login(self.user)
        self.data = {'preset_topic': PRODUCT_SCALE_TOPICS[0][0], 'level': 'senior'}

    def create_session(self):
        response = self.client.post(reverse('product_scale_create'), self.data)
        self.assertEqual(response.status_code, 302)
        return MockInterviewSession.objects.get(user=self.user)

    def test_setup_and_presets_need_no_resume_or_company(self):
        response = self.client.get(reverse('product_scale_start'))
        self.assertContains(response, 'Product-scale interview')
        self.assertContains(response, 'No coding or industry research is required.')
        self.assertContains(response, reverse('product_scale_create'))
        for topic, label in PRODUCT_SCALE_TOPICS:
            self.assertContains(response, label)
            form = MockInterviewStartForm({'preset_topic': topic, 'level': 'senior'}, track='product_scale')
            self.assertTrue(form.is_valid(), form.errors)
            self.assertLessEqual(len(form.cleaned_data['topic']), 1000)
        original = self.client.get(reverse('mock_interview_start'))
        self.assertContains(original, 'URL Shortener')
        self.assertNotContains(original, 'Workshop booking service')
        self.assertEqual(list(MockInterviewStartForm().fields['preset_topic'].choices), list(SYSTEM_DESIGN_TOPICS))

    def test_track_saved_and_visible_in_room_history_and_feedback(self):
        session = self.create_session()
        self.assertEqual(session.track, 'product_scale')
        self.assertEqual(session.topic, PRODUCT_SCALE_TOPICS[0][0])
        room = self.client.get(reverse('mock_interview_room', args=[session.uuid]))
        self.assertContains(room, 'Product-scale design')
        self.assertContains(room, reverse('product_scale_start'))
        self.assertContains(self.client.get(reverse('mock_interview_history')), 'Product-scale design')
        self.assertNotContains(self.client.get(reverse('mock_interview_start')), session.topic)
        session.status = 'completed'
        session.feedback_json = {'overall_score': 75, 'summary': 'Clear trade-offs.'}
        session.save()
        feedback = self.client.get(reverse('mock_interview_feedback', args=[session.uuid]))
        self.assertContains(feedback, reverse('product_scale_start'))
        self.assertIn('Product-scale design', coaching_prompt(session))

    def test_custom_question_and_default_preset(self):
        form = MockInterviewStartForm({'custom_topic': 'Design a small repair booking product.', 'level': 'mid'}, track='product_scale')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['topic_source'], 'custom')
        self.assertEqual(form.cleaned_data['topic'], 'Design a small repair booking product.')
        form = MockInterviewStartForm({'level': 'mid'}, track='product_scale')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['topic'], PRODUCT_SCALE_TOPICS[0][0])

    def test_invalid_submission_stays_in_track(self):
        for data in ({'preset_topic': 'Rate Limiter', 'level': 'senior'},
                     {'custom_topic': 'x' * 1001, 'level': 'mid'},
                     {'level': 'invalid'}):
            response = self.client.post(reverse('product_scale_create'), data)
            self.assertEqual(response.status_code, 400)
            self.assertContains(response, reverse('product_scale_create'), status_code=400)
        self.assertFalse(MockInterviewSession.objects.exists())

    def test_route_controls_track_and_old_submissions_keep_default(self):
        response = self.client.post(reverse('mock_interview_create'), {'preset_topic': 'Rate Limiter', 'level': 'senior', 'track': 'product_scale'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(MockInterviewSession.objects.get().track, 'system_design')

    def test_access_and_csrf(self):
        self.assertEqual(self.client.get(reverse('product_scale_create')).status_code, 405)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(reverse('product_scale_create'), self.data).status_code, 403)
        session = self.create_session()
        other = get_user_model().objects.create_user('another', password='test')
        EarlyAccessUser.objects.create(user=other, email='other@example.test', is_beta_active=True)
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('mock_interview_room', args=[session.uuid])).status_code, 404)
        self.assertEqual(self.client.get(reverse('simulator_room', args=[session.uuid])).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('product_scale_start')).status_code, 302)

    def test_continuation_preserves_track_and_context(self):
        session = self.create_session()
        session.status = 'completed'
        session.transcript_text = 'Candidate: I propose a single service.'
        session.save()
        response = self.client.post(reverse('mock_interview_continue_free_style', args=[session.uuid]))
        self.assertEqual(response.status_code, 302)
        continuation = MockInterviewSession.objects.get(continued_from=session)
        self.assertEqual(continuation.track, 'product_scale')
        self.assertEqual(continuation.transcript_text, session.transcript_text)

    @override_settings(OPENAI_API_KEY='test')
    def test_provider_uses_track_prompt_and_feedback_rubric(self):
        session = self.create_session()
        session.transcript_text = 'Candidate: I would clarify cancellation rules.'
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"value":"token"}'
        with patch('apps.product.services.urllib.request.urlopen', return_value=response) as call:
            create_mock_interview_realtime_token(self.user, session)
        instructions = json.loads(call.call_args.args[0].data)['session']['instructions']
        self.assertIn('product-scale design review', instructions)
        self.assertIn('Continue from the conversation above', instructions)
        self.assertIn('clarify cancellation rules', instructions)
        self.assertIn('one concrete requirement change at a time', instructions)
        feedback = {'overall_score': 70, 'summary': 'Good clarification.', 'strengths': [], 'gaps': [], 'missed_topics': [], 'better_answer_outline': [], 'next_practice_steps': []}
        with patch('openai.OpenAI') as api:
            api.return_value.chat.completions.create.return_value.choices[0].message.content = json.dumps(feedback)
            self.assertEqual(generate_mock_interview_feedback(session), feedback)
        messages = api.return_value.chat.completions.create.call_args.kwargs['messages']
        self.assertEqual(messages[0]['content'], PRODUCT_SCALE_FEEDBACK_INSTRUCTIONS)
        self.assertEqual(json.loads(messages[1]['content'])['topic'], session.topic)
        original = build_mock_interview_instructions('Rate Limiter', 'Senior')
        self.assertNotIn('product-scale design review', original)
