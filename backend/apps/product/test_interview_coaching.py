from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from apps.website.models import EarlyAccessUser
from .models import MockInterviewSession, MockInterviewTurn
from .interview_coaching import coaching_prompt


class InterviewCoachingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='coaching')
        EarlyAccessUser.objects.create(user=self.user, email='coaching@example.test', is_beta_active=True)
        self.client.force_login(self.user)

    def create(self):
        return MockInterviewSession.objects.create(user=self.user, topic='Practice topic', status='completed', feedback_json={'summary': 'Improve clarity', 'gaps': ['Tradeoffs'], 'overall_score': 60})

    def test_feedback_offers_full_prompt(self):
        session = self.create()
        MockInterviewTurn.objects.create(session=session, role='user', text='My actual answer')
        response = self.client.get(reverse('mock_interview_feedback', kwargs={'session_uuid': session.uuid}))
        self.assertContains(response, 'Work on my gaps in ChatGPT')
        prompt = response.context['coaching_prompt']
        self.assertIn('My actual answer', prompt)
        self.assertIn('Improve clarity', prompt)
        self.assertIn('Tradeoffs', prompt)
        self.assertIn('one practice question at a time', prompt)
        self.assertIn('no-store', response['Cache-Control'])

    def test_no_handoff_for_unfinished_or_missing_feedback(self):
        session = self.create()
        session.status = 'active'
        self.assertEqual(coaching_prompt(session), '')
        session.status = 'completed'
        session.feedback_json = {}
        self.assertEqual(coaching_prompt(session), '')

    def test_full_transcript_fallback_without_truncation(self):
        session = self.create()
        session.transcript_text = 'Long answer ' * 15000 + 'FINAL ANSWER'
        prompt = coaching_prompt(session)
        self.assertIn(session.transcript_text, prompt)
        self.assertIn('FINAL ANSWER', prompt)

    def test_transcript_is_escaped_and_other_users_denied(self):
        session = self.create()
        MockInterviewTurn.objects.create(session=session, role='user', text='</script><script>alert(1)</script>')
        url = reverse('mock_interview_feedback', kwargs={'session_uuid': session.uuid})
        response = self.client.get(url)
        self.assertNotContains(response, '</script><script>alert(1)</script>')
        self.assertContains(response, r'\u003C/script\u003E')
        other = get_user_model().objects.create_user(username='other-coaching')
        session.user = other
        session.save()
        self.assertEqual(self.client.get(url).status_code, 404)
