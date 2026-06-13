from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone

from .forms import EarlyAccessForm
from .forms import PricingSuggestionForm
from .models import BlogPost
from .models import EarlyAccessUser
from .models import PricingSuggestion


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
