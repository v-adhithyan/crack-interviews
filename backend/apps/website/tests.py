from django.contrib import admin
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages import get_messages
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import override_settings
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .admin import BlogPostAdmin
from .admin import EarlyAccessUserAdmin
from .models import BlogPost
from .models import EarlyAccessUser
from .models import PricingSuggestion
from .models import WebsitePage
from .views import server_error


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

    def test_blog_detail_renders_markdown_content(self):
        post = BlogPost.objects.create(
            title="Markdown Lessons",
            slug="markdown-lessons",
            excerpt="Markdown blog content.",
            content="## Main idea\n\n- Keep it tight\n- Show impact\n\nUse `metrics`.",
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
        )

        response = self.client.get(reverse("blog_detail", kwargs={"slug": post.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<h2>Main idea</h2>", html=True)
        self.assertContains(response, "<li>Keep it tight</li>", html=True)
        self.assertContains(response, "<code>metrics</code>", html=True)

    def test_blog_detail_keeps_plain_text_rendering(self):
        post = BlogPost.objects.create(
            title="Plain Lessons",
            slug="plain-lessons",
            excerpt="Plain blog content.",
            content="First paragraph.\n\nSecond paragraph.",
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
        )

        response = self.client.get(reverse("blog_detail", kwargs={"slug": post.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<p>First paragraph.</p>", html=True)
        self.assertContains(response, "<p>Second paragraph.</p>", html=True)

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


class PricingSuggestionTests(TestCase):
    def test_pricing_page_renders_slider_form(self):
        response = self.client.get(reverse("pricing_page"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Free for the first 50 beta users.")
        self.assertContains(response, 'name="price"')
        self.assertContains(response, 'name="no_of_months"')

    def test_pricing_submission_saves_suggestion_with_metadata(self):
        response = self.client.post(
            reverse("pricing_page"),
            {"price": "499", "no_of_months": "6"},
            HTTP_USER_AGENT="PricingTestAgent",
            REMOTE_ADDR="203.0.113.10",
            follow=True,
        )

        self.assertRedirects(response, reverse("pricing_page"))
        suggestion = PricingSuggestion.objects.get()
        self.assertEqual(suggestion.price, 499)
        self.assertEqual(suggestion.no_of_months, 6)
        self.assertEqual(suggestion.ip_address, "203.0.113.10")
        self.assertEqual(suggestion.metadata["user_agent"], "PricingTestAgent")
        self.assertContains(response, "You suggested ₹499 for 6 months.")
        self.assertNotContains(response, 'name="price"')

    def test_pricing_submission_validates_ranges(self):
        response = self.client.post(reverse("pricing_page"), {"price": "1000", "no_of_months": "13"})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PricingSuggestion.objects.exists())
        self.assertIn("Please choose a price no more than ₹999.", [str(message) for message in get_messages(response.wsgi_request)])

    def test_pricing_page_hides_form_when_session_already_suggested(self):
        session = self.client.session
        session.save()
        PricingSuggestion.objects.create(
            price=299,
            no_of_months=3,
            session_key=session.session_key,
            metadata={},
        )

        response = self.client.get(reverse("pricing_page"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You suggested ₹299 for 3 months.")
        self.assertNotContains(response, 'name="price"')

    def test_pricing_page_hides_form_when_ip_already_suggested(self):
        PricingSuggestion.objects.create(
            price=199,
            no_of_months=1,
            ip_address="203.0.113.11",
            metadata={},
        )

        response = self.client.get(reverse("pricing_page"), REMOTE_ADDR="203.0.113.11")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You suggested ₹199 for 1 month.")
        self.assertNotContains(response, 'name="price"')


class WebsiteContentSeedTests(TestCase):
    def test_seed_website_content_creates_pages_and_blog_posts(self):
        call_command("seed_website_content")

        self.assertTrue(WebsitePage.objects.filter(slug="about", is_published=True).exists())
        self.assertTrue(WebsitePage.objects.filter(slug="faq", is_published=True).exists())
        self.assertTrue(BlogPost.objects.filter(slug="resume-tips-for-software-engineers", status=BlogPost.Status.PUBLISHED).exists())
        self.assertTrue(BlogPost.objects.filter(slug="interview-tips-for-software-engineers", status=BlogPost.Status.PUBLISHED).exists())

        about_response = self.client.get(reverse("about_page"))
        faq_response = self.client.get(reverse("faq_page"))
        resume_response = self.client.get(reverse("blog_detail", kwargs={"slug": "resume-tips-for-software-engineers"}))
        interview_response = self.client.get(reverse("blog_detail", kwargs={"slug": "interview-tips-for-software-engineers"}))

        self.assertContains(about_response, "Adhithyan Vijayakumar")
        self.assertContains(about_response, "linkedin.com/in/adhithyan-vijayakumar")
        self.assertContains(faq_response, "What is HackerLeap?")
        self.assertContains(resume_response, "Keep your resume tight.")
        self.assertContains(interview_response, "LinkedIn Easy Apply")

    def test_footer_links_to_seeded_content_routes(self):
        response = self.client.get(reverse("home_page"))

        self.assertContains(response, reverse("about_page"))
        self.assertContains(response, reverse("faq_page"))
        self.assertContains(response, reverse("blog_detail", kwargs={"slug": "resume-tips-for-software-engineers"}))
        self.assertContains(response, reverse("blog_detail", kwargs={"slug": "interview-tips-for-software-engineers"}))


class SeoRobotsTests(TestCase):
    def test_sitemap_lists_public_website_urls(self):
        WebsitePage.objects.create(
            title="About HackerLeap",
            slug="about",
            page_type=WebsitePage.PageType.ABOUT,
            excerpt="About excerpt.",
            content="About content.",
            is_published=True,
        )
        WebsitePage.objects.create(
            title="FAQ",
            slug="faq",
            page_type=WebsitePage.PageType.FAQ,
            excerpt="FAQ excerpt.",
            content="FAQ content.",
            is_published=False,
        )
        BlogPost.objects.create(
            title="Published post",
            slug="published-post",
            excerpt="Published excerpt.",
            content="Published content.",
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        BlogPost.objects.create(
            title="Draft post",
            slug="draft-post",
            excerpt="Draft excerpt.",
            content="Draft content.",
            status=BlogPost.Status.DRAFT,
        )

        response = self.client.get(reverse("sitemap_xml"))
        body = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/xml")
        self.assertIn("http://testserver/", body)
        self.assertIn("http://testserver/blog/", body)
        self.assertIn("http://testserver/pricing/", body)
        self.assertIn("http://testserver/privacy/", body)
        self.assertIn("http://testserver/about/", body)
        self.assertIn("http://testserver/blog/published-post/", body)
        self.assertNotIn("http://testserver/faq/", body)
        self.assertNotIn("http://testserver/blog/draft-post/", body)

    def test_robots_txt_allows_crawlers_and_links_sitemap(self):
        response = self.client.get(reverse("robots_txt"))
        body = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertIn("User-agent: *", body)
        self.assertIn("Allow: /", body)
        self.assertIn("Sitemap: http://testserver/sitemap.xml", body)


class ErrorPageTests(TestCase):
    @override_settings(DEBUG=False)
    def test_website_404_uses_shared_error_page(self):
        response = self.client.get("/missing-website-page/")

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Page not found", status_code=404)
        self.assertContains(response, "HackerLeap", status_code=404)
        self.assertContains(response, "Go home", status_code=404)

    @override_settings(DEBUG=False)
    def test_product_404_uses_shared_error_page(self):
        response = self.client.get("/app/missing-product-page/")

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Page not found", status_code=404)
        self.assertContains(response, "HackerLeap", status_code=404)

    def test_500_uses_shared_error_page(self):
        request = RequestFactory().get("/app/")
        request.user = AnonymousUser()

        response = server_error(request)

        self.assertEqual(response.status_code, 500)
        self.assertIn("Something went wrong", response.content.decode())
        self.assertIn("HackerLeap", response.content.decode())
