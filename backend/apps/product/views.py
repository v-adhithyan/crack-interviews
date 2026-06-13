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


class ProductLoginView(LoginView):
    authentication_form = ProductLoginForm
    template_name = "product/auth/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        return self.get_redirect_url() or reverse_lazy("product_dashboard")


@product_access_required
def dashboard(request):
    return render(request, "product/dashboard.html")


def early_access_signup(request, token):
    early_access_user = get_object_or_404(EarlyAccessUser, signup_token=token, is_beta_active=True)

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
            early_access_user.save(update_fields=("user", "date_of_birth", "signup_completed_at", "updated_at"))
            login(request, user)
            messages.success(request, "Welcome to HackerLeap. Your beta access is active.")
            return redirect("product_dashboard")

    return render(request, "product/auth/signup.html", {"form": form, "early_access_user": early_access_user})
