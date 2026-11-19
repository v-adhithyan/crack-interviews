from pathlib import Path

from django.db import migrations
from django.utils import timezone


def publish_resume_comparisons(apps, schema_editor):
    BlogPost = apps.get_model("website", "BlogPost")
    posts = BlogPost.objects.using(schema_editor.connection.alias)
    content_dir = Path(__file__).resolve().parents[1] / "content"
    published_at = timezone.now()

    for slug in (
        "hackerleap-vs-canva",
        "hackerleap-vs-novoresume",
        "hackerleap-vs-resume-io",
        "hackerleap-vs-teal",
        "hackerleap-vs-zety",
    ):
        title, _, excerpt, _, body = (content_dir / f"{slug}.md").read_text(
            encoding="utf-8"
        ).split("\n", 4)
        posts.get_or_create(
            slug=slug,
            defaults={
                "title": title.removeprefix("# "),
                "excerpt": excerpt.removeprefix("Excerpt: "),
                "content": body.rstrip("\n"),
                "author_name": "HackerLeap team",
                "status": "published",
                "published_at": published_at,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("website", "0007_earlyaccessuser_invite_user")]

    # Keep posts on rollback because they may have been edited in the CMS.
    operations = [migrations.RunPython(publish_resume_comparisons, migrations.RunPython.noop)]
