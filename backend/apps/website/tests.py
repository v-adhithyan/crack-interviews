from django.contrib import admin
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from .admin import EarlyAccessUserAdmin
from .models import EarlyAccessUser


class EarlyAccessSignupTests(TestCase):
    def test_home_page_saves_valid_email(self):
        response = self.client.post(reverse("home_page"), {"email": "USER@example.COM"}, follow=True)

        self.assertRedirects(response, reverse("home_page"))
        self.assertTrue(EarlyAccessUser.objects.filter(email="user@example.com").exists())
        self.assertIn(
            "Thanks! Adi will personally verify your request and email you instructions to access your account.",
            [str(message) for message in get_messages(response.wsgi_request)],
        )

    def test_duplicate_email_does_not_create_another_record(self):
        EarlyAccessUser.objects.create(email="user@example.com")

        response = self.client.post(reverse("home_page"), {"email": "USER@example.COM"})

        self.assertRedirects(response, reverse("home_page"))
        self.assertEqual(EarlyAccessUser.objects.filter(email="user@example.com").count(), 1)

    def test_invalid_email_shows_error_message(self):
        response = self.client.post(reverse("home_page"), {"email": "not-an-email"})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(EarlyAccessUser.objects.exists())
        self.assertIn("Please enter a valid email address.", [str(message) for message in get_messages(response.wsgi_request)])


class EarlyAccessAdminTests(TestCase):
    def test_early_access_user_is_registered_in_admin(self):
        self.assertIsInstance(admin.site._registry[EarlyAccessUser], EarlyAccessUserAdmin)
