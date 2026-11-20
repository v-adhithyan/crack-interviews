from django.apps import apps
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from .models import AIIntegration


class AdminModelVisibilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.superuser = users.create_superuser(username="admin")
        cls.staff = users.create_user(username="staff", is_staff=True)
        cls.member = users.create_user(username="member")
        cls.integration = AIIntegration.objects.create(
            user=cls.member, encrypted_api_key="example-encrypted-value"
        )

    def test_all_project_models_have_accessible_admin_lists(self):
        self.client.force_login(self.superuser)
        index = self.client.get(reverse("admin:index"))
        for app_label in ("core", "product", "website"):
            for model in apps.get_app_config(app_label).get_models():
                with self.subTest(model=model._meta.label):
                    self.assertTrue(admin.site.is_registered(model))
                    url = reverse(f"admin:{app_label}_{model._meta.model_name}_changelist")
                    self.assertContains(index, f'href="{url}"')
                    self.assertEqual(self.client.get(url).status_code, 200)

    def test_staff_can_view_integration_without_exposing_or_changing_key(self):
        url = reverse("admin:product_aiintegration_change", args=[self.integration.pk])
        changelist = reverse("admin:product_aiintegration_changelist")
        permission = Permission.objects.get(
            content_type__app_label="product", codename="view_aiintegration"
        )
        self.member.user_permissions.add(permission)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(url).status_code, 302)

        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.staff.user_permissions.add(permission)

        for user in (self.staff, self.superuser):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(url)
                self.assertContains(response, self.member.username)
                self.assertNotContains(response, 'id="id_encrypted_api_key"')
                self.assertNotContains(response, self.integration.encrypted_api_key)
                self.assertEqual(self.client.post(url, {"user": self.staff.pk}).status_code, 403)
                response = self.client.get(changelist, {"encrypted_api_key__startswith": "example"})
                self.assertEqual(response.status_code, 400)

        self.integration.refresh_from_db()
        self.assertEqual(self.integration.user, self.member)
