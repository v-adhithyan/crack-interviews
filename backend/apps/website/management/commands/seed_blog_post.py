from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.website.models import BlogPost


class Command(BaseCommand):
    help = "Create or update a published dummy blog post for local testing."

    def handle(self, *args, **options):
        post, created = BlogPost.objects.update_or_create(
            slug="dummy-resume-match-guide",
            defaults={
                "title": "How to Make Your Resume Easier to Match",
                "excerpt": "A short guide to writing resumes that work better with ATS systems and hiring teams.",
                "content": (
                    "Start with the role you want, then shape your resume around evidence.\n\n"
                    "Strong bullets make the scope, action, and result easy to scan. A recruiter should understand "
                    "what you built, why it mattered, and how it moved the product or team forward.\n\n"
                    "The goal is not to stuff keywords. The goal is to make relevance obvious. Use the language of "
                    "the job description only when it truthfully describes work you have done.\n\n"
                    "Before applying, compare your resume against the role and look for missing signals: systems, "
                    "tools, scale, ownership, and outcomes. Then rewrite the weakest bullets until the match is clear."
                ),
                "author_name": "Adhi",
                "status": BlogPost.Status.PUBLISHED,
                "published_at": timezone.now(),
                "seo_title": "Resume Matching Tips for Software Engineers",
                "seo_description": "A practical dummy blog post about improving resume match quality for software engineering roles.",
            },
        )

        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} dummy blog post: /blog/{post.slug}/"))
