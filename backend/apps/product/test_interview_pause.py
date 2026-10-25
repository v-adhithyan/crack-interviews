from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from apps.website.models import EarlyAccessUser
from .models import MockInterviewSession, InterviewSimulatorSession, UserFeatureFlags


class InterviewPauseTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='pause-user')
        EarlyAccessUser.objects.create(user=self.user, email='pause@example.test', is_beta_active=True)
        self.client.force_login(self.user)
        self.now = timezone.now()

    def create(self, model=MockInterviewSession, **kwargs):
        return model.objects.create(user=self.user, topic='Interview', status='active', started_at=self.now - timedelta(minutes=10), **kwargs)

    def url(self, action, session):
        prefix = 'simulator_' if isinstance(session, InterviewSimulatorSession) else 'mock_interview_'
        return reverse(prefix + action, kwargs={'session_uuid': session.uuid})

    def test_pause_freezes_clock_and_is_idempotent_for_both_types(self):
        for model in (MockInterviewSession, InterviewSimulatorSession):
            session = self.create(model)
            with patch('django.utils.timezone.now', return_value=self.now):
                response = self.client.post(self.url('pause', session))
            self.assertEqual(response.status_code, 200)
            session.refresh_from_db()
            self.assertEqual(session.status, 'paused')
            with patch('django.utils.timezone.now', return_value=self.now + timedelta(hours=2)):
                self.assertEqual(session.remaining_seconds, 3000)
                again = self.client.post(self.url('pause', session))
                self.assertEqual(again.json()['remaining_seconds'], 3000)
                self.assertTrue(self.client.get(self.url('state', session)).json()['paused'])
            session.refresh_from_db()
            self.assertEqual(session.paused_at, self.now)

    @patch('apps.product.views.create_mock_interview_realtime_token', return_value={'value': 'short-lived'})
    def test_resume_excludes_break_and_does_not_charge_quota(self, token):
        for model in (MockInterviewSession, InterviewSimulatorSession):
            session = self.create(model)
            with patch('django.utils.timezone.now', return_value=self.now):
                self.client.post(self.url('pause', session))
            with patch('django.utils.timezone.now', return_value=self.now + timedelta(hours=2)):
                response = self.client.post(self.url('token', session))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['interview_state']['remaining_seconds'], 3000)
            session.refresh_from_db()
            self.assertEqual(session.paused_duration, timedelta(hours=2))
            self.assertIsNone(session.paused_at)
            self.assertEqual(session.status, 'active')
        self.assertFalse(UserFeatureFlags.objects.filter(user=self.user).exists())

    @patch('apps.product.views.create_mock_interview_realtime_token', side_effect=ValidationError('Reconnect your integration.'))
    def test_failed_resume_does_not_unfreeze_timer(self, token):
        session = self.create(paused_at=self.now)
        with patch('django.utils.timezone.now', return_value=self.now + timedelta(hours=1)):
            self.assertEqual(self.client.post(self.url('token', session)).status_code, 400)
            session.refresh_from_db()
            self.assertEqual(session.remaining_seconds, 3000)
            self.assertEqual(session.paused_at, self.now)

    def test_reject_unstarted_expired_and_completed(self):
        for values in ({'started_at': None, 'status': 'created'}, {'started_at': self.now-timedelta(hours=2)}, {'status': 'completed'}):
            session = self.create()
            for key, value in values.items():
                setattr(session, key, value)
            session.save()
            self.assertEqual(self.client.post(self.url('pause', session)).status_code, 409)

    def test_pause_requires_post_csrf_and_ownership(self):
        session = self.create()
        url = self.url('pause', session)
        self.assertEqual(self.client.get(url).status_code, 405)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        self.assertEqual(strict.post(url).status_code, 403)
        other = get_user_model().objects.create_user(username='other-pause')
        session.user = other
        session.save()
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertEqual(self.client.get(self.url('state', session)).status_code, 404)

    def test_free_style_can_pause(self):
        session = self.create(mode='free')
        self.assertEqual(self.client.post(self.url('pause', session)).status_code, 200)
        session.refresh_from_db()
        self.assertFalse(session.is_time_expired)

    def test_room_distinguishes_paused_from_disconnected(self):
        session = self.create()
        response = self.client.get(self.url('room', session))
        self.assertContains(response, 'The interview clock is still running')
        self.client.post(self.url('pause', session))
        self.assertContains(self.client.get(self.url('room', session)), 'Interview paused. Audio is disconnected and the interview clock is stopped.')

    @patch('apps.product.views.generate_mock_interview_feedback', return_value={'summary': 'Done'})
    def test_can_end_paused_interview_and_cannot_resume_completed(self, feedback):
        session = self.create(paused_at=self.now)
        self.assertEqual(self.client.post(self.url('finish', session)).status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.status, 'completed')
        self.assertEqual(self.client.post(self.url('token', session)).status_code, 400)
        self.assertEqual(self.client.post(self.url('pause', session)).status_code, 409)

    @patch('apps.product.views.create_mock_interview_realtime_token', return_value={'value': 'short-lived'})
    def test_multiple_breaks_accumulate(self, token):
        session = self.create()
        for minutes, action in [(0, 'pause'), (5, 'token'), (7, 'pause'), (17, 'token')]:
            with patch('django.utils.timezone.now', return_value=self.now + timedelta(minutes=minutes)):
                self.assertEqual(self.client.post(self.url(action, session)).status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.paused_duration, timedelta(minutes=15))
        with patch('django.utils.timezone.now', return_value=self.now + timedelta(minutes=17)):
            self.assertEqual(session.remaining_seconds, 48*60)
