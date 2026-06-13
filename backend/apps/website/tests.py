from django.contrib import admin
from django.contrib.messages import get_messages
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .admin import BlogPostAdmin
from .admin import EarlyAccessUserAdmin
from .models import BlogPost
from .models import EarlyAccessUser


class EarlyAccessSignupTests(TestCase):
    def test_home_page_saves_valid_email(self):
        response = self.client.post(reverse("home_page"), {"email": "USER@example.COM"}, follow=True)

        self.assertRedirects(response, reverse("home_page"))
        self.assertTrue(EarlyAccessUser.objects.filter(email="user@example.com").exists())
        self.assertIn(
            "Thanks! Adhi will personally verify your request and email you instructions to access your account.",
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


class BlogPostTests(TestCase):
    def test_blog_index_lists_published_posts_only(self):
        BlogPost.objects.create(
            title="Published post",
            slug="published-post",
            excerpt="A useful published excerpt.",
            content="Published content.",
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        BlogPost.objects.create(
            title="Draft post",
            slug="draft-post",
            excerpt="A draft excerpt.",
            content="Draft content.",
            status=BlogPost.Status.DRAFT,
        )

        response = self.client.get(reverse("blog_index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Published post")
        self.assertNotContains(response, "Draft post")

    def test_blog_detail_renders_published_post(self):
        post = BlogPost.objects.create(
            title="Resume Lessons",
            slug="resume-lessons",
            excerpt="Better resume thinking for engineers.",
            content="First paragraph.\n\nSecond paragraph.",
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
            seo_title="Resume Lessons SEO",
            seo_description="Resume SEO description.",
        )

        response = self.client.get(reverse("blog_detail", kwargs={"slug": post.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Resume Lessons")
        self.assertContains(response, "First paragraph.")
        self.assertContains(response, "Resume SEO description.")

    def test_blog_detail_does_not_render_drafts(self):
        post = BlogPost.objects.create(
            title="Draft post",
            slug="draft-post",
            excerpt="A draft excerpt.",
            content="Draft content.",
            status=BlogPost.Status.DRAFT,
        )

        response = self.client.get(reverse("blog_detail", kwargs={"slug": post.slug}))

        self.assertEqual(response.status_code, 404)

    def test_publishing_sets_published_at(self):
        post = BlogPost.objects.create(
            title="Publish me",
            slug="publish-me",
            excerpt="Publish excerpt.",
            content="Publish content.",
            status=BlogPost.Status.PUBLISHED,
        )

        self.assertIsNotNone(post.published_at)


class BlogPostAdminTests(TestCase):
    def test_blog_post_is_registered_in_admin(self):
        self.assertIsInstance(admin.site._registry[BlogPost], BlogPostAdmin)

    def test_superuser_can_preview_draft_post(self):
        user = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password",
        )
        post = BlogPost.objects.create(
            title="Draft preview",
            slug="draft-preview",
            excerpt="A private draft excerpt.",
            content="Private draft content.",
            status=BlogPost.Status.DRAFT,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("admin:website_blogpost_preview", args=[post.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Draft preview")
        self.assertContains(response, "Private draft content.")

    def test_staff_user_cannot_preview_draft_post(self):
        user = get_user_model().objects.create_user(
            username="staff",
            email="staff@example.com",
            password="password",
            is_staff=True,
        )
        post = BlogPost.objects.create(
            title="Draft preview",
            slug="draft-preview",
            excerpt="A private draft excerpt.",
            content="Private draft content.",
            status=BlogPost.Status.DRAFT,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("admin:website_blogpost_preview", args=[post.pk]))

        self.assertEqual(response.status_code, 403)

    def test_admin_change_page_includes_preview_link(self):
        user = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password",
        )
        post = BlogPost.objects.create(
            title="Draft preview",
            slug="draft-preview",
            excerpt="A private draft excerpt.",
            content="Private draft content.",
            status=BlogPost.Status.DRAFT,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("admin:website_blogpost_change", args=[post.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("admin:website_blogpost_preview", args=[post.pk]))
        self.assertContains(response, "Preview blog post")


class LegalPageTests(TestCase):
    def test_legal_pages_render(self):
        pages = (
            ("privacy_policy", "Privacy Policy"),
            ("terms_of_service", "Terms of Service"),
            ("refund_policy", "Refund Policy"),
        )

        for route_name, heading in pages:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, heading)

    def test_footer_links_to_legal_pages(self):
        response = self.client.get(reverse("home_page"))

        self.assertContains(response, reverse("privacy_policy"))
        self.assertContains(response, reverse("terms_of_service"))
        self.assertContains(response, reverse("refund_policy"))
