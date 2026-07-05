import json

from django.conf import settings
from django.http import FileResponse
from django.http import Http404
from django.http import HttpResponseBadRequest
from django.http import JsonResponse
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
from django.views.decorators.http import require_POST

from apps.website.models import EarlyAccessUser
from apps.core.jobs import enqueue_background_job

from .decorators import product_access_required
from .forms import AnalysisPromptForm
from .forms import AnalysisResultForm
from .forms import EarlyAccessSignupForm
from .forms import MockInterviewStartForm
from .forms import ProductLoginForm
from .forms import ResumeUploadForm
from .models import Resume
from .models import ResumeAnalysis
from .models import MockInterviewSession
from .models import MockInterviewTurn
from .services import build_resume_match_prompt
from .services import create_mock_interview_realtime_token
from .services import generate_mock_interview_feedback
from .services import get_configured_resume_analysis_mode
from .services import get_effective_resume_analysis_mode
from .services import get_user_feature_flags
from .services import reserve_resume_analysis_ai_quota
from .services import run_resume_match_analysis
from .services import user_has_coding_platform_access


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


def user_mock_interview_queryset(user):
    queryset = MockInterviewSession.objects.select_related("user")
    if not user.is_staff:
        queryset = queryset.filter(user=user)
    return queryset


def get_visible_mock_interview_or_404(user, session_uuid):
    return get_object_or_404(user_mock_interview_queryset(user), uuid=session_uuid)


def user_display_label(user):
    full_name = (user.get_full_name() or "").strip()
    return full_name or user.email or user.username


def is_manual_ai_mode(user):
    return get_effective_resume_analysis_mode(user) == "manual"


def selected_ai_mode(user):
    return get_effective_resume_analysis_mode(user)


@product_access_required
def code_platform_redirect(request):
    if not user_has_coding_platform_access(request.user):
        messages.error(request, "Coding platform access is not enabled for your account yet.")
        return redirect("product_dashboard")
    return redirect(settings.HACKERLEAP_CODE)


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
                configured_ai_mode = get_configured_resume_analysis_mode(request.user)
                ai_mode = selected_ai_mode(request.user)
                manual_due_to_quota = configured_ai_mode in {"chatgpt", "claude"} and ai_mode == "manual"
                if ai_mode in {"chatgpt", "claude"}:
                    if reserve_resume_analysis_ai_quota(request.user):
                        analysis = ResumeAnalysis.objects.create(
                            user=request.user,
                            resume=resume,
                            job_description=job_description,
                            resume_text=resume.parsed_text,
                            generated_prompt=build_resume_match_prompt(job_description, resume.parsed_text),
                            status=ResumeAnalysis.Status.QUEUED,
                            ai_provider=ai_mode,
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
                    ai_mode = "manual"
                    manual_due_to_quota = True

                try:
                    analysis_result = run_resume_match_analysis(
                        job_description=job_description,
                        resume_text=resume.parsed_text,
                        mode=ai_mode,
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

                if manual_due_to_quota:
                    messages.success(request, "Daily AI analysis limit reached. Manual prompt generated for now; AI analysis resets after 24 hours.")
                else:
                    messages.success(request, "Prompt generated. Copy it, use it with your preferred AI tool, then paste the JSON result below.")
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
            "is_manual_ai_mode": is_manual_ai_mode(request.user),
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
def mock_interview_start(request):
    resume = user_resume(request.user)
    feature_flags = get_user_feature_flags(request.user, create=True)
    feature_flags.reset_mock_interview_usage_if_expired()
    form = MockInterviewStartForm()
    sessions = user_mock_interview_queryset(request.user)[:5]
    return render(
        request,
        "product/mock_interview_start.html",
        {
            "resume": resume,
            "form": form,
            "recent_sessions": sessions,
            "active_nav": "mock_interview",
            "quota_remaining": feature_flags.mock_interview_quota_remaining,
        },
    )


@product_access_required
@require_POST
def mock_interview_create(request):
    form = MockInterviewStartForm(request.POST)
    if form.is_valid():
        session = MockInterviewSession.objects.create(
            user=request.user,
            topic_source=form.cleaned_data["topic_source"],
            topic=form.cleaned_data["topic"],
            level=form.cleaned_data["level"],
        )
        return redirect("mock_interview_room", session_uuid=session.uuid)

    resume = user_resume(request.user)
    feature_flags = get_user_feature_flags(request.user, create=True)
    messages.error(request, "Please choose a topic or enter a custom system design question.")
    return render(
        request,
        "product/mock_interview_start.html",
        {
            "resume": resume,
            "form": form,
            "recent_sessions": user_mock_interview_queryset(request.user)[:5],
            "active_nav": "mock_interview",
            "quota_remaining": feature_flags.mock_interview_quota_remaining,
        },
        status=400,
    )


@product_access_required
def mock_interview_room(request, session_uuid):
    session = get_visible_mock_interview_or_404(request.user, session_uuid)
    if session.status == MockInterviewSession.Status.COMPLETED:
        return redirect("mock_interview_feedback", session_uuid=session.uuid)

    return render(
        request,
        "product/mock_interview_room.html",
        {
            "resume": user_resume(request.user),
            "session": session,
            "active_nav": "mock_interview",
            "duration_seconds": int(MockInterviewSession.DURATION.total_seconds()),
            "remaining_seconds": session.remaining_seconds,
            "mock_interview_user_label": user_display_label(session.user),
        },
    )


@product_access_required
@require_POST
def mock_interview_continue_free_style(request, session_uuid):
    source_session = get_visible_mock_interview_or_404(request.user, session_uuid)
    if source_session.is_free_style or (source_session.status != MockInterviewSession.Status.COMPLETED and not source_session.is_time_expired):
        messages.error(request, "Free style continuation is available after a timed interview ends.")
        if source_session.status == MockInterviewSession.Status.COMPLETED:
            return redirect("mock_interview_feedback", session_uuid=source_session.uuid)
        return redirect("mock_interview_room", session_uuid=source_session.uuid)

    transcript_text = "\n".join(f"{turn.get_role_display()}: {turn.text}" for turn in source_session.turns.all())
    if not transcript_text:
        transcript_text = source_session.transcript_text

    continuation = MockInterviewSession.objects.create(
        user=source_session.user,
        continued_from=source_session,
        mode=MockInterviewSession.Mode.FREE,
        topic_source=source_session.topic_source,
        topic=source_session.topic,
        level=source_session.level,
        transcript_text=transcript_text,
    )
    MockInterviewTurn.objects.bulk_create(
        MockInterviewTurn(
            session=continuation,
            role=turn.role,
            text=turn.text,
            occurred_at=turn.occurred_at,
        )
        for turn in source_session.turns.all()
    )
    messages.success(request, "Free style continuation created. Resume when you are ready.")
    return redirect("mock_interview_room", session_uuid=continuation.uuid)


@product_access_required
@require_POST
def mock_interview_token(request, session_uuid):
    session = get_visible_mock_interview_or_404(request.user, session_uuid)
    if session.status == MockInterviewSession.Status.COMPLETED:
        return JsonResponse({"detail": "This interview has already ended."}, status=400)
    if not session.is_free_style and session.status == MockInterviewSession.Status.ACTIVE and session.is_time_expired:
        return JsonResponse({"detail": "This interview has reached the 60 minute time limit."}, status=400)

    should_start_session = session.status == MockInterviewSession.Status.CREATED
    feature_flags = None
    if should_start_session and not session.is_free_style:
        feature_flags = get_user_feature_flags(request.user, create=True)
        if not feature_flags.can_run_mock_interview():
            return JsonResponse({"detail": "Daily mock interview limit reached. Please try again after 24 hours."}, status=429)

    try:
        token_payload = create_mock_interview_realtime_token(request.user, session)
    except (ImproperlyConfigured, ValidationError) as exc:
        session.status = MockInterviewSession.Status.FAILED
        session.error_message = str(exc)
        session.ended_at = timezone.now()
        session.save(update_fields=("status", "error_message", "ended_at", "updated_at"))
        return JsonResponse({"detail": str(exc)}, status=400)
    except Exception:
        session.status = MockInterviewSession.Status.FAILED
        session.error_message = "Unable to create voice interview session right now."
        session.ended_at = timezone.now()
        session.save(update_fields=("status", "error_message", "ended_at", "updated_at"))
        return JsonResponse({"detail": session.error_message}, status=500)

    if session.status == MockInterviewSession.Status.CREATED:
        if not session.is_free_style and (feature_flags is None or not feature_flags.consume_mock_interview_quota()):
            return JsonResponse({"detail": "Daily mock interview limit reached. Please try again after 24 hours."}, status=429)
        session.status = MockInterviewSession.Status.ACTIVE
        session.started_at = timezone.now()
        session.save(update_fields=("status", "started_at", "updated_at"))

    return JsonResponse(token_payload)


@product_access_required
@require_POST
def mock_interview_turns(request, session_uuid):
    session = get_visible_mock_interview_or_404(request.user, session_uuid)
    if session.status == MockInterviewSession.Status.COMPLETED or (not session.is_free_style and session.is_time_expired):
        return HttpResponseBadRequest("This interview has ended.")
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON.")

    role = payload.get("role")
    text = (payload.get("text") or "").strip()
    if role == "assistant":
        role = MockInterviewTurn.Role.INTERVIEWER
    if role not in {MockInterviewTurn.Role.USER, MockInterviewTurn.Role.INTERVIEWER} or not text:
        return HttpResponseBadRequest("Turn role and text are required.")

    turn = MockInterviewTurn.objects.create(session=session, role=role, text=text)
    session.transcript_text = "\n".join(f"{item.get_role_display()}: {item.text}" for item in session.turns.all())
    session.save(update_fields=("transcript_text", "updated_at"))
    return JsonResponse({"id": turn.id, "status": "saved"})


@product_access_required
@require_POST
def mock_interview_finish(request, session_uuid):
    session = get_visible_mock_interview_or_404(request.user, session_uuid)
    if session.status == MockInterviewSession.Status.COMPLETED and session.feedback_json:
        return JsonResponse({"feedback_url": reverse("mock_interview_feedback", kwargs={"session_uuid": session.uuid})})

    session.transcript_text = "\n".join(f"{turn.get_role_display()}: {turn.text}" for turn in session.turns.all())
    try:
        session.feedback_json = generate_mock_interview_feedback(session)
        session.status = MockInterviewSession.Status.COMPLETED
        session.ended_at = timezone.now()
        session.error_message = ""
        session.save(update_fields=("transcript_text", "feedback_json", "status", "ended_at", "error_message", "updated_at"))
    except (ImproperlyConfigured, ValidationError) as exc:
        session.status = MockInterviewSession.Status.FAILED
        session.error_message = str(exc)
        session.ended_at = timezone.now()
        session.save(update_fields=("transcript_text", "status", "error_message", "ended_at", "updated_at"))
        return JsonResponse({"detail": str(exc)}, status=400)
    except Exception:
        session.status = MockInterviewSession.Status.FAILED
        session.error_message = "Unable to generate feedback right now. Please try again."
        session.ended_at = timezone.now()
        session.save(update_fields=("transcript_text", "status", "error_message", "ended_at", "updated_at"))
        return JsonResponse({"detail": session.error_message}, status=500)

    return JsonResponse({"feedback_url": reverse("mock_interview_feedback", kwargs={"session_uuid": session.uuid})})


@product_access_required
def mock_interview_history(request):
    return render(
        request,
        "product/mock_interview_history.html",
        {
            "resume": user_resume(request.user),
            "sessions": user_mock_interview_queryset(request.user),
            "active_nav": "mock_interview_history",
        },
    )


@product_access_required
def mock_interview_feedback(request, session_uuid):
    session = get_visible_mock_interview_or_404(request.user, session_uuid)
    return render(
        request,
        "product/mock_interview_feedback.html",
        {
            "resume": user_resume(request.user),
            "session": session,
            "feedback": session.feedback_json or {},
            "active_nav": "mock_interview_history",
        },
    )


@product_access_required
def current_resume_content(request):
    resume = user_resume(request.user)
    if not resume:
        raise Http404

    return serve_resume_content(resume)


@product_access_required
def resume_content(request, resume_uuid):
    resume = get_object_or_404(Resume, uuid=resume_uuid)
    if resume.user_id != request.user.id and not request.user.is_staff:
        raise Http404

    return serve_resume_content(resume)


def serve_resume_content(resume):
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
