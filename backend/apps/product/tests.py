import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.test import TestCase
from django.urls import reverse

from apps.website.models import EarlyAccessUser

from .models import Resume


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
        self.assertContains(response, "Upload Your Resume")

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


class ResumeUploadTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_media_root = tempfile.mkdtemp()
        cls.override = override_settings(MEDIA_ROOT=cls.test_media_root)
        cls.override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.override.disable()
        shutil.rmtree(cls.test_media_root, ignore_errors=True)

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="resume@example.com",
            email="resume@example.com",
            password="Password1!",
        )
        self.client.force_login(self.user)

    def test_dashboard_shows_empty_resume_state(self):
        response = self.client.get(reverse("product_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-menu-toggle')
        self.assertContains(response, 'class="user-menu"')
        self.assertContains(response, ">Logout<")
        self.assertContains(response, "Choose your resume PDF")
        self.assertContains(response, "Select PDF")
        self.assertContains(response, "favicon.svg")
        self.assertContains(response, "No analyses yet")
        self.assertNotContains(response, "Ankit_Resume.pdf")

    def test_pdf_resume_upload_creates_resume_for_user(self):
        resume_file = SimpleUploadedFile(
            "adhi_resume.pdf",
            b"%PDF-1.4\nresume\n%%EOF",
            content_type="application/pdf",
        )

        response = self.client.post(reverse("product_dashboard"), {"resume": resume_file}, follow=True)

        resume = Resume.objects.get(user=self.user)
        self.assertRedirects(response, reverse("product_dashboard"))
        self.assertEqual(resume.original_filename, "adhi_resume.pdf")
        self.assertEqual(resume.content_type, "application/pdf")
        self.assertContains(response, "adhi_resume.pdf")
        self.assertContains(response, reverse("resume_content", kwargs={"resume_uuid": resume.uuid}))
        self.assertContains(response, 'target="_blank"')
        self.assertContains(response, "Start New Analysis")
        self.assertNotContains(response, "Choose your resume PDF")

    def test_non_pdf_resume_is_rejected(self):
        resume_file = SimpleUploadedFile(
            "resume.txt",
            b"not a pdf",
            content_type="text/plain",
        )

        response = self.client.post(reverse("product_dashboard"), {"resume": resume_file})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Resume.objects.filter(user=self.user).exists())
        self.assertContains(response, "Please upload a PDF resume.")

    def test_resume_larger_than_one_mb_is_rejected(self):
        resume_file = SimpleUploadedFile(
            "large_resume.pdf",
            b"x" * (1024 * 1024 + 1),
            content_type="application/pdf",
        )

        response = self.client.post(reverse("product_dashboard"), {"resume": resume_file})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Resume.objects.filter(user=self.user).exists())
        self.assertContains(response, "Please upload a PDF no larger than 1 MB.")

    def test_upload_replaces_existing_resume_for_user(self):
        first_file = SimpleUploadedFile("first.pdf", b"%PDF-1.4\nfirst\n%%EOF", content_type="application/pdf")
        second_file = SimpleUploadedFile("second.pdf", b"%PDF-1.4\nsecond\n%%EOF", content_type="application/pdf")

        self.client.post(reverse("product_dashboard"), {"resume": first_file})
        first_uuid = Resume.objects.get(user=self.user).uuid
        self.client.post(reverse("product_dashboard"), {"resume": second_file})
        resume = Resume.objects.get(user=self.user)

        self.assertEqual(Resume.objects.filter(user=self.user).count(), 1)
        self.assertEqual(resume.original_filename, "second.pdf")
        self.assertNotEqual(resume.uuid, first_uuid)
        self.assertEqual(self.client.get(reverse("resume_content", kwargs={"resume_uuid": first_uuid})).status_code, 404)

    def test_uploaded_resume_filename_has_tooltip(self):
        long_name = "adhithyan_vijayakumar_backend_engineer_resume_2026_final.pdf"
        resume_file = SimpleUploadedFile(long_name, b"%PDF-1.4\nresume\n%%EOF", content_type="application/pdf")
        self.client.post(reverse("product_dashboard"), {"resume": resume_file})

        response = self.client.get(reverse("product_dashboard"))

        self.assertContains(response, 'class="filename-with-tooltip"', count=2)
        self.assertContains(response, f'title="{long_name}"', count=2)
        self.assertContains(response, f'data-tooltip="{long_name}"', count=2)

    def test_user_can_view_own_resume_content_with_private_cache_headers(self):
        resume_file = SimpleUploadedFile("own.pdf", b"%PDF-1.4\nown\n%%EOF", content_type="application/pdf")
        self.client.post(reverse("product_dashboard"), {"resume": resume_file})
        resume = Resume.objects.get(user=self.user)

        response = self.client.get(reverse("resume_content", kwargs={"resume_uuid": resume.uuid}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response["Cache-Control"], "private, max-age=31536000, immutable")
        self.assertEqual(response["ETag"], f'"resume-{resume.uuid}"')
        self.assertIn("inline", response["Content-Disposition"])
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.4\nown\n%%EOF")

    def test_user_cannot_view_another_users_resume_content(self):
        other_user = get_user_model().objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="Password1!",
        )
        resume = Resume.objects.create(
            user=other_user,
            file=SimpleUploadedFile("other.pdf", b"%PDF-1.4\nother\n%%EOF", content_type="application/pdf"),
            original_filename="other.pdf",
            content_type="application/pdf",
            size=22,
        )

        response = self.client.get(reverse("resume_content", kwargs={"resume_uuid": resume.uuid}))

        self.assertEqual(response.status_code, 404)

    def test_staff_can_view_any_resume_content(self):
        other_user = get_user_model().objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="Password1!",
        )
        staff_user = get_user_model().objects.create_user(
            username="staff-viewer",
            email="staff-viewer@example.com",
            password="Password1!",
            is_staff=True,
        )
        resume = Resume.objects.create(
            user=other_user,
            file=SimpleUploadedFile("other.pdf", b"%PDF-1.4\nother\n%%EOF", content_type="application/pdf"),
            original_filename="other.pdf",
            content_type="application/pdf",
            size=22,
        )
        self.client.force_login(staff_user)

        response = self.client.get(reverse("resume_content", kwargs={"resume_uuid": resume.uuid}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.4\nother\n%%EOF")


class EarlyAccessSignupTests(TestCase):
    def test_invite_signup_creates_plain_user_and_logs_in(self):
        early_access_user = EarlyAccessUser.objects.create(email="invited@example.com", is_beta_active=False)

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
        self.assertTrue(early_access_user.is_beta_active)
        self.assertIsNotNone(early_access_user.signup_completed_at)
        self.assertRedirects(response, reverse("product_dashboard"))

    def test_invite_signup_requires_strong_password(self):
        early_access_user = EarlyAccessUser.objects.create(email="invited@example.com", is_beta_active=False)

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

    def test_active_invite_does_not_render_signup(self):
        early_access_user = EarlyAccessUser.objects.create(email="invited@example.com", is_beta_active=True)

        response = self.client.get(reverse("early_access_signup", kwargs={"token": early_access_user.signup_token}))

        self.assertEqual(response.status_code, 404)
