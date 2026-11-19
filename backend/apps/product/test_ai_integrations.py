from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.website.models import EarlyAccessUser

from .ai_integrations import get_openai_api_key
from .models import AIIntegration, MockInterviewSession, ResumeAnalysis
from .services import get_effective_resume_analysis_mode
from .tasks import run_resume_analysis


@override_settings(
    AI_USE_SHARED_KEY_FOR_LOCAL_DEV=False,
    OPENAI_API_KEY="shared-test-key",
    SECRET_KEY="test-only-django-secret-for-ai-integrations",
)
class AIIntegrationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("external", "external@example.com")
        EarlyAccessUser.objects.create(user=self.user, email=self.user.email, is_beta_active=True)
        self.url = reverse("ai_integration_settings")
        self.client.force_login(self.user)

    def save_key(self, key):
        return self.client.post(self.url, {"provider": "chatgpt", "api_key": key})

    def test_shared_key_eligibility(self):
        self.assertRaisesMessage(ImproperlyConfigured, "Set your ChatGPT API key", get_openai_api_key, self.user)
        self.user.email = "person@HACKERLEAP.COM"
        self.assertEqual(get_openai_api_key(self.user), "shared-test-key")
        self.user.email = "person@hackerleap.com.example.org"
        self.assertRaises(ImproperlyConfigured, get_openai_api_key, self.user)
        with override_settings(AI_USE_SHARED_KEY_FOR_LOCAL_DEV=True):
            self.assertEqual(get_openai_api_key(self.user), "shared-test-key")
        self.user.is_staff = True
        self.assertEqual(get_openai_api_key(self.user), "shared-test-key")

    @override_settings(HACKERLEAP_AI_MODE="chatgpt")
    def test_effective_mode_falls_back_until_personal_key_is_configured(self):
        self.assertEqual(get_effective_resume_analysis_mode(self.user), "manual")
        self.assertRedirects(self.save_key("test-personal-key"), self.url)
        self.assertEqual(get_effective_resume_analysis_mode(self.user), "chatgpt")

    def test_mock_interview_voice_and_feedback_direct_user_to_settings_without_key(self):
        session = MockInterviewSession.objects.create(user=self.user, topic="URL Shortener")

        for endpoint in ("mock_interview_token", "mock_interview_finish"):
            with self.subTest(endpoint=endpoint):
                response = self.client.post(reverse(endpoint, kwargs={"session_uuid": session.uuid}))
                self.assertEqual(response.status_code, 400)
                self.assertIn("Set your ChatGPT API key in Settings → Integrations → AI", response.json()["detail"])

    def test_settings_are_access_controlled(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        outsider = get_user_model().objects.create_user("outsider")
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_save_replace_and_reject_unsupported_provider_without_exposing_keys(self):
        first, second = "first-personal-key", "second-personal-key"
        self.assertRedirects(self.save_key(first), self.url)
        ciphertext = AIIntegration.objects.get(user=self.user).encrypted_api_key
        self.assertNotIn(first, ciphertext)
        self.assertEqual(get_openai_api_key(self.user), first)
        rejected = self.client.post(self.url, {"provider": "claude", "api_key": "unsupported-personal-key"})
        self.assertContains(rejected, "Claude is currently unsupported")
        self.assertNotContains(rejected, "unsupported-personal-key")
        self.assertEqual(AIIntegration.objects.get(user=self.user).encrypted_api_key, ciphertext)
        self.assertRedirects(self.save_key(second), self.url)
        response = self.client.get(self.url)
        self.assertContains(response, "Replace API key")
        self.assertNotContains(response, first)
        self.assertNotContains(response, second)
        self.assertEqual(get_openai_api_key(self.user), second)

    @patch("openai.OpenAI")
    def test_worker_uses_only_job_owners_key_and_sanitizes_provider_failure(self, openai):
        other = get_user_model().objects.create_user("other", "other@example.com")
        self.save_key("owner-test-key")
        analyses = [
            ResumeAnalysis.objects.create(user=user, status="queued", ai_provider="chatgpt")
            for user in [other, self.user]
        ]
        run_resume_analysis(analyses[0].pk)
        openai.assert_not_called()
        analyses[0].refresh_from_db()
        self.assertIn("Set your ChatGPT API key", analyses[0].error_message)

        openai.side_effect = RuntimeError("Provider error mentioning owner-test-key")
        run_resume_analysis(analyses[1].pk)
        openai.assert_called_once_with(api_key="owner-test-key")
        analyses[1].refresh_from_db()
        self.assertEqual(analyses[1].status, "failed")
        self.assertNotIn("owner-test-key", analyses[1].error_message)
