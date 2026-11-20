from django.apps import apps
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import NoReverseMatch, reverse


class AdminModelVisibilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = get_user_model().objects.create_superuser(username="admin")

    def test_admin_lists_match_model_visibility(self):
        hidden_models = {
            "product.AIIntegration",
            "product.AnalysisFollowup",
            "product.InterviewSimulatorSession",
            "product.MockInterviewSession",
            "product.MockInterviewTurn",
        }
        self.client.force_login(self.superuser)
        index = self.client.get(reverse("admin:index"))
        for app_label in ("core", "product", "website"):
            for model in apps.get_app_config(app_label).get_models():
                with self.subTest(model=model._meta.label):
                    list_name = f"admin:{app_label}_{model._meta.model_name}_changelist"
                    if model._meta.label in hidden_models:
                        self.assertFalse(admin.site.is_registered(model))
                        self.assertNotContains(index, f'href="/admin/{app_label}/{model._meta.model_name}/"')
                        with self.assertRaises(NoReverseMatch):
                            reverse(list_name)
                        continue

                    self.assertTrue(admin.site.is_registered(model))
                    url = reverse(list_name)
                    self.assertContains(index, f'href="{url}"')
                    self.assertEqual(self.client.get(url).status_code, 200)
