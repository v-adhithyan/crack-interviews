import re

import markdown
from django import template
from django.template.defaultfilters import linebreaks
from django.utils.safestring import mark_safe


register = template.Library()


MARKDOWN_PATTERNS = [
    re.compile(r"^\s{0,3}#{1,6}\s+\S", re.MULTILINE),
    re.compile(r"^\s{0,3}[-*+]\s+\S", re.MULTILINE),
    re.compile(r"^\s{0,3}\d+\.\s+\S", re.MULTILINE),
    re.compile(r"^\s{0,3}>\s+\S", re.MULTILINE),
    re.compile(r"^\s{0,3}```", re.MULTILINE),
    re.compile(r"^\s{0,3}~~~", re.MULTILINE),
    re.compile(r"\[[^\]]+\]\([^)]+\)"),
    re.compile(r"!\[[^\]]*\]\([^)]+\)"),
    re.compile(r"`[^`\n]+`"),
    re.compile(r"(\*\*|__)[^\n]+(\*\*|__)"),
    re.compile(r"^\s*\|?.+\|\s*$\n^\s*\|?\s*:?-{3,}:?\s*\|", re.MULTILINE),
]


def looks_like_markdown(value):
    return any(pattern.search(value) for pattern in MARKDOWN_PATTERNS)


@register.filter
def render_blog_content(value):
    if not value:
        return ""

    text = str(value)
    if not looks_like_markdown(text):
        return mark_safe(linebreaks(text, autoescape=True))

    rendered = markdown.markdown(
        text,
        extensions=["extra", "sane_lists"],
        output_format="html5",
    )
    return mark_safe(rendered)
