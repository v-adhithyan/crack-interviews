from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from .models import PublicBuilderCounter
from .public_resume_views import SIGNUP_COUNTER_KEY


class PublicSignupLimitTests(TestCase):
    def setUp(self):
        cache.delete(SIGNUP_COUNTER_KEY)
        self.addCleanup(cache.delete, SIGNUP_COUNTER_KEY)
        self.url = reverse('public_signup')
        # Two minutes before IST midnight, still the same UTC date after reset.
        self.clock = patch('apps.product.public_resume_views.timezone.now',
                           return_value=datetime(2026, 11, 19, 18, 28, tzinfo=timezone.utc))
        self.now = self.clock.start()
        self.addCleanup(self.clock.stop)

    def signup(self, number, **overrides):
        data = {
            'username': f'candidate{number}',
            'email': f'candidate{number}@example.com',
            'password1': 'ExamplePass!100',
            'password2': 'ExamplePass!100',
        }
        with self.captureOnCommitCallbacks(execute=True):
            return Client().post(self.url, {**data, **overrides}, REMOTE_ADDR=f'192.0.2.{number}')

    def test_ten_successes_close_signup_and_midnight_reopens_it(self):
        for number in range(1, 11):
            self.assertContains(Client().get(self.url), 'name="username"')
            self.assertRedirects(self.signup(number), reverse('resume_builder_list'),
                                 fetch_redirect_response=False)

        with self.assertLogs('apps.product.public_resume_views', level='INFO') as logs:
            with self.assertNumQueries(2) as queries:
                page = Client().get(self.url + '?transfer=ignored')
                rejected = self.signup(11)
            for query in queries.captured_queries:
                self.assertIn('FROM "website_blogpost"', query['sql'])
        self.assertEqual(len(logs.records), 2)
        for response in (page, rejected):
            self.assertContains(response, '12:00 AM, 20 November 2026', status_code=429)
            self.assertContains(response, 'IST', status_code=429)
            self.assertNotContains(response, '<form', status_code=429)
            self.assertEqual(response['Retry-After'], '120')
            self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(get_user_model().objects.count(), 10)

        self.now.return_value += timedelta(minutes=2)
        self.assertContains(Client().get(self.url), 'name="username"')
        self.assertEqual(self.signup(11).status_code, 302)
        self.assertEqual(PublicBuilderCounter.objects.get(key=SIGNUP_COUNTER_KEY).count, 1)

    def test_cold_cache_post_and_get_enforce_the_database_cap(self):
        for number in range(1, 11):
            self.assertEqual(self.signup(number).status_code, 302)

        cache.delete(SIGNUP_COUNTER_KEY)
        self.assertEqual(self.signup(11).status_code, 429)
        with self.assertNumQueries(1) as queries:
            self.assertEqual(Client().get(self.url).status_code, 429)
        self.assertIn('FROM "website_blogpost"', queries.captured_queries[0]['sql'])

        cache.delete(SIGNUP_COUNTER_KEY)
        self.assertEqual(Client().get(self.url).status_code, 429)
        with self.assertNumQueries(1) as queries:
            self.assertEqual(self.signup(11).status_code, 429)
        self.assertIn('FROM "website_blogpost"', queries.captured_queries[0]['sql'])

    def test_invalid_and_duplicate_submissions_do_not_use_daily_slots(self):
        self.assertContains(self.signup(1, password2='different'), 'didn’t match')
        self.assertEqual(self.signup(2).status_code, 302)
        self.assertContains(self.signup(3, email='CANDIDATE2@example.com'),
                            'An account already exists')
        self.assertEqual(PublicBuilderCounter.objects.get(key=SIGNUP_COUNTER_KEY).count, 1)

    def test_existing_per_ip_limit_does_not_use_daily_slots(self):
        for _ in range(5):
            self.assertEqual(self.signup(1, password2='different').status_code, 200)
        response = self.signup(1)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response['Retry-After'], '60')
        self.assertEqual(PublicBuilderCounter.objects.get(key=SIGNUP_COUNTER_KEY).count, 0)

    def test_rolled_back_tenth_signup_does_not_close_registration(self):
        PublicBuilderCounter.objects.create(
            key=SIGNUP_COUNTER_KEY, count=9,
            expires_at=self.now.return_value + timedelta(minutes=2),
        )
        with patch('apps.product.public_resume_views.login', side_effect=RuntimeError('login failed')):
            with self.assertRaisesMessage(RuntimeError, 'login failed'):
                self.signup(10)

        self.assertIsNone(cache.get(SIGNUP_COUNTER_KEY))
        self.assertContains(Client().get(self.url), 'name="username"')
        self.assertFalse(get_user_model().objects.filter(username='candidate10').exists())
        self.assertEqual(PublicBuilderCounter.objects.get(key=SIGNUP_COUNTER_KEY).count, 9)
