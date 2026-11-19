from django import template
from django.utils import timezone

from ..models import BlogPost


register = template.Library()

RESUME_COMPARISON_LABELS = {
    "hackerleap-vs-canva": "HackerLeap vs. Canva",
    "hackerleap-vs-novoresume": "HackerLeap vs. Novorésumé",
    "hackerleap-vs-resume-io": "HackerLeap vs. Resume.io",
    "hackerleap-vs-teal": "HackerLeap vs. Teal",
    "hackerleap-vs-zety": "HackerLeap vs. Zety",
}


@register.simple_tag
def footer_resume_comparisons():
    published_slugs = BlogPost.objects.filter(
        slug__in=RESUME_COMPARISON_LABELS,
        status=BlogPost.Status.PUBLISHED,
        published_at__lte=timezone.now(),
    ).order_by("slug").values_list("slug", flat=True)
    return [(slug, RESUME_COMPARISON_LABELS[slug]) for slug in published_slugs]
