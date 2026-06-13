from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.website.models import EarlyAccessUser


class ProductAccessTests(TestCase):
    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("product_dashboard"))

        self.assertRedirects(response, f"{reverse('login')}?next={reverse('product_dashboard')}")

    def test_staff_user_can_access_product_dashboard(self):
        user = get_user_model().objects.create_user(
            username="staff",
            email="staff@example.com",
            password="Password1!",
            is_staff=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("product_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Start New Analysis")

    def test_regular_user_can_access_product_dashboard(self):
        user = get_user_model().objects.create_user(
            username="regular@example.com",
            email="regular@example.com",
            password="Password1!",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("product_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recent Analysis")


class EarlyAccessSignupTests(TestCase):
    def test_invite_signup_creates_plain_user_and_logs_in(self):
        early_access_user = EarlyAccessUser.objects.create(email="invited@example.com", is_beta_active=True)

        response = self.client.post(
            reverse("early_access_signup", kwargs={"token": early_access_user.signup_token}),
            {
                "email": early_access_user.email,
                "date_of_birth": "1995-06-13",
                "password1": "StrongPass1!",
                "password2": "StrongPass1!",
            },
            follow=True,
        )

        user = get_user_model().objects.get(email="invited@example.com")
        early_access_user.refresh_from_db()
        self.assertEqual(early_access_user.date_of_birth.isoformat(), "1995-06-13")
        self.assertEqual(early_access_user.user, user)
        self.assertIsNotNone(early_access_user.signup_completed_at)
        self.assertRedirects(response, reverse("product_dashboard"))

    def test_invite_signup_requires_strong_password(self):
        early_access_user = EarlyAccessUser.objects.create(email="invited@example.com", is_beta_active=True)

        response = self.client.post(
            reverse("early_access_signup", kwargs={"token": early_access_user.signup_token}),
            {
                "email": early_access_user.email,
                "date_of_birth": "1995-06-13",
                "password1": "weakpass",
                "password2": "weakpass",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(email="invited@example.com").exists())
        self.assertContains(response, "Password must include at least one uppercase letter.")

    def test_inactive_invite_does_not_render_signup(self):
        early_access_user = EarlyAccessUser.objects.create(email="invited@example.com", is_beta_active=False)

        response = self.client.get(reverse("early_access_signup", kwargs={"token": early_access_user.signup_token}))

        self.assertEqual(response.status_code, 404)
