from django.http import FileResponse
from django.http import Http404
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils import timezone

from apps.website.models import EarlyAccessUser

from .decorators import product_access_required
from .forms import EarlyAccessSignupForm
from .forms import ProductLoginForm
from .forms import ResumeUploadForm
from .models import Resume


class ProductLoginView(LoginView):
    authentication_form = ProductLoginForm
    template_name = "product/auth/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        return self.get_redirect_url() or reverse_lazy("product_dashboard")


@product_access_required
def dashboard(request):
    resume = Resume.objects.filter(user=request.user).first()
    form = ResumeUploadForm()

    if request.method == "POST":
        form = ResumeUploadForm(request.POST, request.FILES)
        if form.is_valid():
            form.save(request.user)
            messages.success(request, "Resume uploaded successfully.")
            return redirect("product_dashboard")

        first_error = next(iter(form.errors.values()))[0] if form.errors else "Unable to upload your resume."
        messages.error(request, first_error)

    return render(
        request,
        "product/dashboard.html",
        {
            "resume": resume,
            "resume_form": form,
        },
    )


@product_access_required
def resume_content(request, resume_uuid):
    resume = get_object_or_404(Resume, uuid=resume_uuid)
    if resume.user_id != request.user.id and not request.user.is_staff:
        raise Http404

    response = FileResponse(
        resume.file.open("rb"),
        content_type=resume.content_type or "application/pdf",
        filename=resume.original_filename,
        as_attachment=False,
    )
    response["Cache-Control"] = "private, max-age=31536000, immutable"
    response["ETag"] = f'"resume-{resume.uuid}"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


def early_access_signup(request, token):
    early_access_user = get_object_or_404(EarlyAccessUser, signup_token=token, is_beta_active=False)

    if early_access_user.has_completed_signup:
        messages.info(request, "Your HackerLeap account is already active. Please log in.")
        return redirect("login")

    form = EarlyAccessSignupForm(early_access_user=early_access_user)
    if request.method == "POST":
        form = EarlyAccessSignupForm(request.POST, early_access_user=early_access_user)
        if form.is_valid():
            user = form.save()
            early_access_user.user = user
            early_access_user.date_of_birth = form.cleaned_data["date_of_birth"]
            early_access_user.signup_completed_at = timezone.now()
            early_access_user.is_beta_active = True
            early_access_user.save(update_fields=("user", "date_of_birth", "signup_completed_at", "updated_at", "is_beta_active"))
            login(request, user)
            messages.success(request, "Welcome to HackerLeap. Your beta access is active.")
            return redirect("product_dashboard")

    return render(request, "product/auth/signup.html", {"form": form, "early_access_user": early_access_user})
