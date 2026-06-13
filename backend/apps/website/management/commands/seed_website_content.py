from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.website.models import BlogPost
from apps.website.models import WebsitePage


ABOUT_HTML = """
<p>HackerLeap is built by <a href="https://www.linkedin.com/in/adhithyan-vijayakumar-7bb10b69/" target="_blank" rel="noopener">Adhithyan Vijayakumar</a>, a software engineer with around eight years of experience building software across companies like Zoho, Vimeo, Udemy, and HappyFox.</p>
<p>He has been on both sides of the hiring grind: preparing, applying, interviewing, clearing rounds, getting rejected, and trying again. That experience matters, because job search pain is rarely abstract. It is the quiet frustration of sending applications into the void, reading vague ATS rejection signals, and not knowing what to fix next.</p>
<p>In the AI era, this has become even noisier. A resume can be rejected for reasons that sound generic, incomplete, or impossible to act on. HackerLeap exists to make that process more actionable: understand the match, improve the resume, and apply with more confidence.</p>
<p>This was not built as a weekend landing page. Adhithyan has used the product himself day to day for the past year before making it available in beta. The goal is simple: build something practical for software engineers who want clearer feedback before they apply.</p>
"""

FAQ_HTML = """
<h2>What is HackerLeap?</h2>
<p>HackerLeap helps software engineers compare resumes against job descriptions, identify missing signals, improve ATS readiness, and prepare with more confidence.</p>
<h2>Is HackerLeap free?</h2>
<p>HackerLeap is free for the first 50 beta users. After that, we plan to keep pricing lean and affordable.</p>
<h2>Does HackerLeap guarantee interviews or job offers?</h2>
<p>No. HackerLeap gives actionable feedback and preparation support, but hiring decisions depend on companies, roles, timing, competition, and many other factors.</p>
<h2>Should I blindly copy AI suggestions?</h2>
<p>No. Treat suggestions as a strong starting point. Review every change and make sure your resume stays truthful, specific, and representative of your real work.</p>
<h2>Who is this built for?</h2>
<p>It is mainly built for software engineers who want to apply more thoughtfully instead of guessing why a resume is not working.</p>
"""

RESUME_TIPS = """
Keep your resume tight. One page is great. Two pages is okay if you truly have enough relevant experience. Beyond that, most readers will not give you the attention you hope for.

Write for busy engineers and recruiters. Everyone is scanning. Use bullet points, keep them crisp, and make the strongest signal easy to notice.

Show impact, not just activity. A line like "improved deployment time by 35%" or "reduced API latency from 900ms to 240ms" is easier to trust than "worked on backend performance." Scope, action, and result are your friends.

Make important impact stand out. If a project moved a metric, saved cost, improved reliability, or unlocked revenue, do not bury it in a long paragraph.

Keep the essentials: your name, email, phone number, LinkedIn, GitHub, portfolio if relevant, education, open source contributions if any, personal projects worth highlighting, and professional experience with impact.

Avoid unnecessary clutter. Hobbies, languages, and unrelated personal details usually do not help in a software engineering resume. Many application systems like Workday and Greenhouse already ask for extra details separately.

At the end of the day, it is your resume. Make it honest, sharp, and easy to remember in a crowded job search world.
"""

INTERVIEW_TIPS = """
Before applying, understand your match. Use HackerLeap to compare your resume with the job description, check the match percentage, and find the missing signals you can honestly improve.

Do not treat LinkedIn Easy Apply as your only strategy. Easy Apply is easy, but getting an interview from it is often not easy. Many candidates never hear back, and some roles may not be actively reviewed.

When LinkedIn provides an external application link, use it. Yes, it takes 5 to 10 minutes. Yes, you may need to answer role-specific questions. That effort is often the difference between casually applying and actually giving yourself a shot.

Prepare from the job description, not from random interview lists alone. Look at the stack, responsibilities, seniority, and domain. Then revise your stories and technical examples around that role.

Use your resume as your interview map. Every bullet point should be something you can explain clearly: what was the problem, what you did, what trade-offs you made, and what changed because of your work.

Confidence does not come from guessing. It comes from doing the preparation, finding the gaps, fixing what you can, and applying with intent.
"""


class Command(BaseCommand):
    help = "Create or update default website pages and blog posts."

    def handle(self, *args, **options):
        pages = [
            {
                "slug": "about",
                "title": "About HackerLeap",
                "page_type": WebsitePage.PageType.ABOUT,
                "excerpt": "Built by a software engineer who has lived the job search grind and wanted clearer, more actionable feedback.",
                "content": ABOUT_HTML.strip(),
                "seo_title": "About HackerLeap",
                "seo_description": "Learn why HackerLeap was built for software engineers applying in the AI era.",
            },
            {
                "slug": "faq",
                "title": "FAQ",
                "page_type": WebsitePage.PageType.FAQ,
                "excerpt": "Quick answers about HackerLeap, beta access, pricing, and how to use the product responsibly.",
                "content": FAQ_HTML.strip(),
                "seo_title": "HackerLeap FAQ",
                "seo_description": "Answers to common questions about HackerLeap resume matching, ATS feedback, beta access, and pricing.",
            },
        ]

        blog_posts = [
            {
                "slug": "resume-tips-for-software-engineers",
                "title": "Resume Tips for Software Engineers",
                "excerpt": "A practical resume guide for software engineers who want to stand out without adding noise.",
                "content": RESUME_TIPS.strip(),
                "seo_title": "Resume Tips for Software Engineers",
                "seo_description": "Practical resume tips for software engineers: impact, bullet points, links, projects, and what to avoid.",
            },
            {
                "slug": "interview-tips-for-software-engineers",
                "title": "Interview Tips for Software Engineers",
                "excerpt": "How to apply with more intent, use match feedback, and prepare from the role instead of guessing.",
                "content": INTERVIEW_TIPS.strip(),
                "seo_title": "Interview Tips for Software Engineers",
                "seo_description": "Interview and application tips for software engineers using role-specific preparation and HackerLeap match feedback.",
            },
        ]

        for page_data in pages:
            page, created = WebsitePage.objects.update_or_create(
                slug=page_data["slug"],
                defaults={**page_data, "is_published": True},
            )
            self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} page: /{page.slug}/"))

        for post_data in blog_posts:
            post, created = BlogPost.objects.update_or_create(
                slug=post_data["slug"],
                defaults={
                    **post_data,
                    "author_name": "Adhi",
                    "status": BlogPost.Status.PUBLISHED,
                    "published_at": timezone.now(),
                },
            )
            self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} blog post: /blog/{post.slug}/"))
