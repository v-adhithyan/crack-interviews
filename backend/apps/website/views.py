from xml.sax.saxutils import escape

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from .forms import EarlyAccessForm
from .forms import PricingSuggestionForm
from .models import BlogPost
from .models import EarlyAccessUser
from .models import PricingSuggestion
from .models import WebsitePage


def get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def build_request_metadata(request):
    headers = {
        key[5:].replace("_", "-").title(): value
        for key, value in request.META.items()
        if key.startswith("HTTP_")
    }
    return {
        "ip_address": get_client_ip(request),
        "remote_addr": request.META.get("REMOTE_ADDR"),
        "x_forwarded_for": request.META.get("HTTP_X_FORWARDED_FOR"),
        "user_agent": request.META.get("HTTP_USER_AGENT", ""),
        "accept_language": request.META.get("HTTP_ACCEPT_LANGUAGE", ""),
        "referer": request.META.get("HTTP_REFERER", ""),
        "path": request.path,
        "method": request.method,
        "headers": headers,
    }


def home_page(request):
    form = EarlyAccessForm()

    if request.method == "POST":
        form = EarlyAccessForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            _, created = EarlyAccessUser.objects.get_or_create(email=email)
            if created:
                messages.success(
                    request,
                    "Thanks! Adhi will personally verify your request and email you instructions to access your account.",
                )
            else:
                messages.info(request, "You're already on the early access list.")
            return redirect("home_page")

        email_errors = form.errors.get("email")
        message = email_errors[0] if email_errors else "Unable to submit your request. Please try again."
        messages.error(request, message)

    return render(request, "website/home.html", {"early_access_form": form})


def blog_index(request):
    posts = BlogPost.objects.filter(status=BlogPost.Status.PUBLISHED, published_at__lte=timezone.now())
    return render(request, "website/blog/index.html", {"posts": posts})


def blog_detail(request, slug):
    post = get_object_or_404(
        BlogPost,
        slug=slug,
        status=BlogPost.Status.PUBLISHED,
        published_at__lte=timezone.now(),
    )
    return render(request, "website/blog/detail.html", {"post": post})


def privacy_policy(request):
    return render(request, "website/legal/privacy.html")


def terms_of_service(request):
    return render(request, "website/legal/terms.html")


def refund_policy(request):
    return render(request, "website/legal/refund.html")


def pricing_page(request):
    if not request.session.session_key:
        request.session.create()

    session_key = request.session.session_key
    ip_address = get_client_ip(request)
    existing_suggestion = PricingSuggestion.objects.filter(session_key=session_key).first()
    if existing_suggestion is None and ip_address:
        existing_suggestion = PricingSuggestion.objects.filter(ip_address=ip_address).first()

    form = PricingSuggestionForm(initial={"price": 199, "no_of_months": 3})

    if request.method == "POST":
        if existing_suggestion:
            messages.info(request, "Thanks, we already received your pricing suggestion.")
            return redirect("pricing_page")

        form = PricingSuggestionForm(request.POST)
        if form.is_valid():
            suggestion = form.save(commit=False)
            suggestion.session_key = session_key
            suggestion.ip_address = ip_address
            suggestion.metadata = build_request_metadata(request)
            suggestion.save()
            messages.success(request, "Thanks! Your pricing suggestion has been recorded.")
            return redirect("pricing_page")

        first_error = next(iter(form.errors.values()))[0] if form.errors else "Please choose a valid pricing suggestion."
        messages.error(request, first_error)

    return render(
        request,
        "website/pricing.html",
        {
            "pricing_form": form,
            "existing_suggestion": existing_suggestion,
        },
    )


def website_page(request, slug):
    page = get_object_or_404(WebsitePage, slug=slug, is_published=True)
    return render(request, "website/page/detail.html", {"page": page})


def sitemap_xml(request):
    now = timezone.now()
    urls = [
        {"loc": request.build_absolute_uri(reverse("home_page")), "changefreq": "weekly", "priority": "1.0"},
        {"loc": request.build_absolute_uri(reverse("blog_index")), "changefreq": "weekly", "priority": "0.8"},
        {"loc": request.build_absolute_uri(reverse("pricing_page")), "changefreq": "monthly", "priority": "0.8"},
        {"loc": request.build_absolute_uri(reverse("privacy_policy")), "changefreq": "yearly", "priority": "0.3"},
        {"loc": request.build_absolute_uri(reverse("terms_of_service")), "changefreq": "yearly", "priority": "0.3"},
        {"loc": request.build_absolute_uri(reverse("refund_policy")), "changefreq": "yearly", "priority": "0.3"},
    ]

    pages = WebsitePage.objects.filter(is_published=True)
    for page in pages:
        route_name = "about_page" if page.slug == "about" else "faq_page" if page.slug == "faq" else None
        if route_name is None:
            continue
        urls.append(
            {
                "loc": request.build_absolute_uri(reverse(route_name)),
                "lastmod": page.updated_at.date().isoformat(),
                "changefreq": "monthly",
                "priority": "0.7",
            }
        )

    posts = BlogPost.objects.filter(status=BlogPost.Status.PUBLISHED, published_at__lte=now)
    for post in posts:
        urls.append(
            {
                "loc": request.build_absolute_uri(reverse("blog_detail", kwargs={"slug": post.slug})),
                "lastmod": post.updated_at.date().isoformat(),
                "changefreq": "monthly",
                "priority": "0.7",
            }
        )

    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url in urls:
        lines.append("  <url>")
        lines.append(f"    <loc>{escape(url['loc'])}</loc>")
        if url.get("lastmod"):
            lines.append(f"    <lastmod>{url['lastmod']}</lastmod>")
        lines.append(f"    <changefreq>{url['changefreq']}</changefreq>")
        lines.append(f"    <priority>{url['priority']}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return HttpResponse("\n".join(lines), content_type="application/xml")


def robots_txt(request):
    sitemap_url = request.build_absolute_uri(reverse("sitemap_xml"))
    content = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            f"Sitemap: {sitemap_url}",
            "",
        ]
    )
    return HttpResponse(content, content_type="text/plain")


def render_error_page(request, status_code, title, message):
    return render(
        request,
        "errors/error.html",
        {
            "status_code": status_code,
            "error_title": title,
            "error_message": message,
            "primary_url": reverse("product_dashboard") if request.user.is_authenticated else reverse("home_page"),
            "primary_label": "Go to dashboard" if request.user.is_authenticated else "Go home",
        },
        status=status_code,
    )


def page_not_found(request, exception):
    return render_error_page(
        request,
        404,
        "Page not found",
        "The page you are looking for does not exist or may have moved.",
    )


def server_error(request):
    return render_error_page(
        request,
        500,
        "Something went wrong",
        "We could not load this page right now. Please try again in a little while.",
    )
