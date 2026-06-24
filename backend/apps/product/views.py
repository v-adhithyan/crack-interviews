from django.http import FileResponse
from django.http import Http404
from django.http import JsonResponse
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.core.exceptions import ImproperlyConfigured
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.urls import reverse_lazy
from django.utils import timezone

from apps.website.models import EarlyAccessUser
from apps.core.jobs import enqueue_background_job

from .decorators import product_access_required
from .forms import AnalysisPromptForm
from .forms import AnalysisResultForm
from .forms import EarlyAccessSignupForm
from .forms import ProductLoginForm
from .forms import QuickRefreshNoteForm
from .forms import ResumeUploadForm
from .models import QuickRefreshNote
from .models import QuickRefreshSettings
from .models import Resume
from .models import ResumeAnalysis
from .services import build_resume_match_prompt
from .services import run_resume_match_analysis


class ProductLoginView(LoginView):
    authentication_form = ProductLoginForm
    template_name = "product/auth/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        return self.get_redirect_url() or reverse_lazy("product_dashboard")


def user_resume(user):
    return Resume.objects.filter(user=user).first()


def user_analysis_queryset(user):
    return ResumeAnalysis.objects.filter(user=user).select_related("resume", "user")


def get_visible_analysis_or_404(user, analysis_uuid):
    queryset = ResumeAnalysis.objects.select_related("resume", "user")
    if not user.is_staff:
        queryset = queryset.filter(user=user)
    return get_object_or_404(queryset, uuid=analysis_uuid)


def is_manual_ai_mode():
    return (settings.HACKERLEAP_AI_MODE or "manual").strip().lower() == "manual"


def selected_ai_mode():
    return (settings.HACKERLEAP_AI_MODE or "manual").strip().lower()


@product_access_required
def dashboard(request):
    resume = user_resume(request.user)
    resume_form = ResumeUploadForm()
    analysis_form = AnalysisPromptForm()
    result_form = AnalysisResultForm()
    user_analyses = user_analysis_queryset(request.user)
    latest_analysis = user_analyses.first()

    if request.method == "POST":
        action = request.POST.get("action", "upload_resume")

        if action == "generate_prompt":
            if not resume:
                messages.error(request, "Please upload your resume before generating a prompt.")
                return redirect("product_dashboard")
            if not resume.parsed_text.strip():
                messages.error(request, "We could not find readable text in your uploaded resume. Please upload a text-based PDF resume.")
                return redirect("product_dashboard")

            analysis_form = AnalysisPromptForm(request.POST)
            if analysis_form.is_valid():
                job_description = analysis_form.cleaned_data["job_description"]
                if selected_ai_mode() in {"chatgpt", "claude"}:
                    analysis = ResumeAnalysis.objects.create(
                        user=request.user,
                        resume=resume,
                        job_description=job_description,
                        resume_text=resume.parsed_text,
                        generated_prompt=build_resume_match_prompt(job_description, resume.parsed_text),
                        status=ResumeAnalysis.Status.QUEUED,
                        ai_provider=selected_ai_mode(),
                    )
                    try:
                        task_id = enqueue_background_job("apps.product.tasks.run_resume_analysis", analysis.id)
                    except Exception as exc:
                        analysis.status = ResumeAnalysis.Status.FAILED
                        analysis.error_message = str(exc) or "Unable to queue analysis right now. Please try again later."
                        analysis.completed_at = timezone.now()
                        analysis.save(update_fields=("status", "error_message", "completed_at", "updated_at"))
                        messages.error(request, "Unable to queue analysis right now. Please try again later.")
                        return redirect("analysis_detail", analysis_uuid=analysis.uuid)
                    analysis.task_id = task_id or ""
                    analysis.save(update_fields=("task_id", "updated_at"))
                    messages.success(request, "Analysis queued. We will update this page as it runs.")
                    return redirect("analysis_detail", analysis_uuid=analysis.uuid)

                try:
                    analysis_result = run_resume_match_analysis(
                        job_description=job_description,
                        resume_text=resume.parsed_text,
                    )
                except (ImproperlyConfigured, NotImplementedError, ValidationError) as exc:
                    messages.error(request, str(exc))
                    return redirect("product_dashboard")
                except Exception:
                    messages.error(request, "Unable to complete AI analysis right now. Please try again later.")
                    return redirect("product_dashboard")

                ResumeAnalysis.objects.create(
                    user=request.user,
                    resume=resume,
                    job_description=job_description,
                    resume_text=resume.parsed_text,
                    generated_prompt=analysis_result.generated_prompt,
                    ai_response_json=analysis_result.ai_response_json,
                    status=ResumeAnalysis.Status.RESULT_ADDED if analysis_result.is_complete else ResumeAnalysis.Status.PROMPT_READY,
                    ai_provider=analysis_result.provider,
                )

                messages.success(request, "Prompt generated. Copy it, run it manually, then paste the JSON result below.")
                return redirect("product_dashboard")

            messages.error(request, "Please complete the analysis inputs.")

        elif action == "save_analysis_json":
            if not latest_analysis:
                messages.error(request, "Generate a prompt before adding analysis JSON.")
                return redirect("product_dashboard")

            result_form = AnalysisResultForm(request.POST)
            if result_form.is_valid():
                latest_analysis.ai_response_json = result_form.parsed_json
                latest_analysis.status = ResumeAnalysis.Status.RESULT_ADDED
                latest_analysis.completed_at = timezone.now()
                latest_analysis.save(update_fields=("ai_response_json", "status", "completed_at", "updated_at"))
                messages.success(request, "Analysis JSON saved.")
                return redirect("product_dashboard")

            messages.error(request, "Please paste valid analysis JSON.")

        else:
            resume_form = ResumeUploadForm(request.POST, request.FILES)
            if resume_form.is_valid():
                success_message = "Resume replaced successfully." if resume else "Resume uploaded successfully."
                resume_form.save(request.user)
                messages.success(request, success_message)
                return redirect("product_dashboard")

            first_error = next(iter(resume_form.errors.values()))[0] if resume_form.errors else "Unable to upload your resume."
            messages.error(request, first_error)

    if latest_analysis and request.method != "POST":
        analysis_form = AnalysisPromptForm(
            initial={
                "job_description": latest_analysis.job_description,
            }
        )

    return render(
        request,
        "product/dashboard.html",
        {
            "resume": resume,
            "resume_form": resume_form,
            "analysis_form": analysis_form,
            "result_form": result_form,
            "latest_analysis": latest_analysis,
            "recent_analyses": user_analyses[:5],
            "active_nav": "dashboard",
            "is_manual_ai_mode": is_manual_ai_mode(),
        },
    )


@product_access_required
def analysis_history(request):
    resume = user_resume(request.user)
    analyses = user_analysis_queryset(request.user)
    return render(
        request,
        "product/analysis_history.html",
        {
            "resume": resume,
            "analyses": analyses,
            "active_nav": "analysis_history",
        },
    )


@product_access_required
def analysis_detail(request, analysis_uuid):
    analysis = get_visible_analysis_or_404(request.user, analysis_uuid)
    resume = user_resume(request.user)
    return render(
        request,
        "product/analysis_detail.html",
        {
            "resume": resume,
            "analysis": analysis,
            "active_nav": "analysis_history",
        },
    )


@product_access_required
def analysis_status(request, analysis_uuid):
    analysis = get_visible_analysis_or_404(request.user, analysis_uuid)
    return JsonResponse(
        {
            "status": analysis.status,
            "label": analysis.progress_label,
            "display_status": analysis.display_status,
            "progress": analysis.progress_percent,
            "is_complete": analysis.status == ResumeAnalysis.Status.RESULT_ADDED,
            "is_failed": analysis.status == ResumeAnalysis.Status.FAILED,
            "error_message": analysis.error_message,
            "detail_url": reverse("analysis_detail", kwargs={"analysis_uuid": analysis.uuid}),
        }
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


@product_access_required
def quick_refresh(request):
    if not request.user.is_staff:
        raise Http404

    settings = QuickRefreshSettings.load()
    if not settings.is_enabled:
        raise Http404

    note, _ = QuickRefreshNote.objects.get_or_create(user=request.user)
    form = QuickRefreshNoteForm(instance=note)

    if request.method == "POST":
        form = QuickRefreshNoteForm(request.POST, instance=note)
        if form.is_valid():
            form.save()
            messages.success(request, "Quick Refresh saved.")
            return redirect("quick_refresh")
        messages.error(request, "Please check the Quick Refresh content.")

    return render(
        request,
        "product/quick_refresh.html",
        {
            "form": form,
            "note": note,
            "resume": user_resume(request.user),
            "active_nav": "quick_refresh",
        },
    )


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
