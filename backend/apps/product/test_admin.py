from datetime import timedelta

from django.apps import apps
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from apps.core.models import AdminApiToken
from apps.product.models import AIIntegration, MockInterviewSession, ResumeDraft


class AdminModelVisibilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = get_user_model().objects.create_superuser(username="admin")

    def test_admin_lists_match_model_visibility(self):
        hidden_models = {
            "product.AIIntegration",
            "product.AnalysisFollowup",
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


class UserRelatedRecordsAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.superuser = users.create_superuser(username="admin")
        cls.staff = users.create_user(username="staff", is_staff=True)
        cls.staff.user_permissions.add(
            Permission.objects.get(content_type__app_label="auth", codename="change_user")
        )
        cls.user = users.create_user(username="target")
        cls.url = reverse("admin:auth_user_change", args=[cls.user.pk])

    def test_limits_each_model_and_orders_by_creation_time_then_primary_key(self):
        now = timezone.now()
        for model in (ResumeDraft, MockInterviewSession):
            records = model.objects.bulk_create([model(user=self.user) for _ in range(32)])
            model.objects.create(user=self.staff)
            model.objects.filter(user=self.user).update(created_at=now)
            model.objects.filter(pk=records[0].pk).update(created_at=now + timedelta(days=1))
            model.objects.filter(pk=records[-1].pk).update(created_at=now - timedelta(days=1))

        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        groups = response.context["user_related_records"]
        self.assertEqual(len(groups), 2)
        for model, group in zip((MockInterviewSession, ResumeDraft), groups):
            expected = list(model.objects.filter(user=self.user).order_by("pk").values_list("pk", flat=True))
            rows = group["records"]
            self.assertEqual([record["pk"] for record in rows], [expected[0], *reversed(expected[2:-1])])
        self.assertIsNone(groups[0]["records"][0]["url"])
        self.assertContains(response, reverse("admin:product_resumedraft_change", args=[groups[1]["records"][0]["pk"]]))

    def test_uses_record_identifiers_without_rendering_credentials(self):
        integration = AIIntegration.objects.create(user=self.user, encrypted_api_key="encrypted-test-value")
        token = AdminApiToken.objects.create(user=self.user)

        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        groups = {str(group["label"]): group["records"] for group in response.context["user_related_records"]}
        self.assertEqual(
            groups[str(AIIntegration._meta.verbose_name_plural)],
            [{"pk": integration.pk, "created_at": None, "url": None}],
        )
        self.assertContains(response, reverse("admin:core_adminapitoken_change", args=[token.pk]))
        self.assertNotContains(response, integration.encrypted_api_key)
        self.assertNotContains(response, token.token)

    def test_staff_with_user_change_permission_cannot_see_related_records(self):
        ResumeDraft.objects.create(user=self.user)
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertNotContains(response, 'id="user-related-records"')
        self.assertNotIn("user_related_records", response.context)

    def test_superuser_sees_empty_state_only_on_existing_user_page(self):
        self.client.force_login(self.superuser)
        self.assertContains(self.client.get(self.url), "No related records.")
        self.assertNotContains(self.client.get(reverse("admin:auth_user_add")), 'id="user-related-records"')
