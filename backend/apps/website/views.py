from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone

from .forms import EarlyAccessForm
from .models import BlogPost
from .models import EarlyAccessUser


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
