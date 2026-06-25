import json
from types import SimpleNamespace

from django.contrib.auth import authenticate, get_user_model
from django.db.models import Count, Exists, OuterRef
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .auth import admin_api_required
from .auth import user_from_authorization_header
from .executor import run_submission
from .models import AdminApiToken, Question, Submission
from .serializers import (
    QuestionDetailSerializer,
    QuestionListSerializer,
    QuestionReferenceSolutionSerializer,
    RevisionSubmissionSerializer,
    SubmissionListSerializer,
    SubmissionSerializer,
)


def questions_with_solved_flag(user):
    accepted = Submission.objects.filter(
        question=OuterRef("pk"),
        user=user,
        kind=Submission.Kind.SUBMIT,
        status=Submission.Status.ACCEPTED,
    )
    revision_marked = accepted.filter(marked_for_revision=True)
    return (
        Question.objects.filter(is_active=True)
        .annotate(solved=Exists(accepted), revision_marked=Exists(revision_marked), test_case_count=Count("test_cases"))
        .order_by("title")
    )


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


@api_view(["POST"])
def auth_login(request):
    identifier = request.data.get("username", "").strip()
    password = request.data.get("password", "")
    if not identifier or not password:
        return Response({"detail": "Username and password are required."}, status=status.HTTP_400_BAD_REQUEST)

    username = identifier
    if "@" in identifier:
        user = get_user_model().objects.filter(email__iexact=identifier).first()
        if user:
            username = user.get_username()

    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({"detail": "Invalid username or password."}, status=status.HTTP_400_BAD_REQUEST)
    if not user.is_staff:
        return Response({"detail": "Admin access is required."}, status=status.HTTP_403_FORBIDDEN)

    token = AdminApiToken.objects.create(user=user)
    return Response(
        {
            "token": token.token,
            "user": {
                "id": user.id,
                "username": user.get_username(),
                "email": user.email,
                "is_staff": user.is_staff,
            },
        }
    )


@api_view(["POST"])
@admin_api_required
def auth_logout(request):
    authorization = request.headers.get("Authorization", "")
    token_value = authorization.removeprefix("Bearer ").strip() if authorization.startswith("Bearer ") else ""
    if token_value:
        AdminApiToken.objects.filter(token=token_value).delete()
    return Response({"status": "ok"})


@api_view(["GET"])
def auth_me(request):
    user = user_from_authorization_header(request)
    if user is None:
        return Response({"detail": "Admin login is required."}, status=status.HTTP_401_UNAUTHORIZED)
    return Response(
        {
            "id": user.id,
            "username": user.get_username(),
            "email": user.email,
            "is_staff": user.is_staff,
        }
    )


@api_view(["GET"])
@admin_api_required
def question_list(request):
    serializer = QuestionListSerializer(questions_with_solved_flag(request.admin_api_user), many=True)
    return Response(serializer.data)


@api_view(["GET"])
@admin_api_required
def question_detail(request, slug):
    question = get_object_or_404(questions_with_solved_flag(request.admin_api_user), slug=slug)
    serializer = QuestionDetailSerializer(question)
    return Response(serializer.data)


@api_view(["GET"])
@admin_api_required
def question_reference_solution(request, slug):
    question = get_object_or_404(Question, slug=slug, is_active=True)
    if not question.java_reference_solution.strip() and not question.python_reference_solution.strip():
        return Response({"detail": "Reference solution is not available for this question."}, status=status.HTTP_404_NOT_FOUND)
    serializer = QuestionReferenceSolutionSerializer(question)
    return Response(serializer.data)


def normalized_language(value):
    language = value or Submission.Language.JAVA
    if language not in Submission.Language.values:
        return None
    return language


def create_and_run_submission(question, code, language, sample_only, kind, user, solve_time_seconds=None):
    test_cases = question.test_cases.all()
    if sample_only:
        test_cases = test_cases.filter(is_sample=True)
    if not test_cases.exists():
        return None

    submission = Submission.objects.create(
        user=user,
        question=question,
        code=code,
        language=language,
        kind=kind,
        solve_time_seconds=solve_time_seconds,
    )
    return run_submission(submission, test_cases)


def custom_test_case_for_question(question, raw_input, expected_output, index=1):
    expected_output = expected_output.strip()
    custom_input = raw_input
    has_expected_output = bool(expected_output)
    if question.execution_mode == Question.ExecutionMode.FUNCTION:
        try:
            function_args = json.loads(raw_input) if raw_input.strip() else []
        except json.JSONDecodeError:
            raise ValueError("Custom input must be valid JSON arguments for function questions.")
        expected_value = None
        if has_expected_output:
            try:
                expected_value = json.loads(expected_output)
            except json.JSONDecodeError:
                expected_value = expected_output
        return SimpleNamespace(
            pk=None,
            name=f"Custom test {index}",
            custom_name=f"Custom test {index}",
            custom_input=custom_input,
            stdin="",
            function_args=function_args,
            expected_value=expected_value,
            expected_output=expected_output,
            has_expected_output=has_expected_output,
            is_sample=False,
            is_hidden=False,
            order=0,
        )

    return SimpleNamespace(
        pk=None,
        name=f"Custom test {index}",
        custom_name=f"Custom test {index}",
        custom_input=custom_input,
        stdin=raw_input,
        function_args=None,
        expected_value=None,
        expected_output=expected_output,
        has_expected_output=has_expected_output,
        is_sample=False,
        is_hidden=False,
        order=0,
    )


def create_and_run_custom_submission(question, code, language, custom_cases, user):
    submission = Submission.objects.create(
        user=user,
        question=question,
        code=code,
        language=language,
        kind=Submission.Kind.CUSTOM,
    )
    test_cases = [
        custom_test_case_for_question(question, str(case.get("input", "")), str(case.get("expected_output", "")), index=index)
        for index, case in enumerate(custom_cases, start=1)
    ]
    return run_submission(submission, test_cases)


def custom_cases_from_request(request):
    raw_cases = request.data.get("test_cases")
    if raw_cases is None:
        return [
            {
                "input": request.data.get("input", ""),
                "expected_output": request.data.get("expected_output", ""),
            }
        ]
    if not isinstance(raw_cases, list):
        raise ValueError("test_cases must be a list.")
    if not raw_cases:
        raise ValueError("Add at least one custom test case.")
    if len(raw_cases) > 5:
        raise ValueError("You can run up to 5 custom test cases at a time.")
    custom_cases = []
    for case in raw_cases:
        if not isinstance(case, dict):
            raise ValueError("Each custom test case must include input and optional expected_output.")
        custom_cases.append(
            {
                "input": case.get("input", ""),
                "expected_output": case.get("expected_output", ""),
            }
        )
    return custom_cases


@api_view(["POST"])
@admin_api_required
def run_code(request, slug):
    question = get_object_or_404(Question, slug=slug, is_active=True)
    code = request.data.get("code", "")
    if not code.strip():
        return Response({"detail": "Code is required."}, status=status.HTTP_400_BAD_REQUEST)
    language = normalized_language(request.data.get("language"))
    if language is None:
        return Response({"detail": "Supported languages are java and python."}, status=status.HTTP_400_BAD_REQUEST)

    submission = create_and_run_submission(question, code, language, sample_only=True, kind=Submission.Kind.RUN, user=request.admin_api_user)
    if submission is None:
        return Response({"detail": "This question has no sample test cases."}, status=status.HTTP_400_BAD_REQUEST)
    return Response(SubmissionSerializer(submission).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@admin_api_required
def run_custom_code(request, slug):
    question = get_object_or_404(Question, slug=slug, is_active=True)
    code = request.data.get("code", "")
    if not code.strip():
        return Response({"detail": "Code is required."}, status=status.HTTP_400_BAD_REQUEST)
    language = normalized_language(request.data.get("language"))
    if language is None:
        return Response({"detail": "Supported languages are java and python."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        custom_cases = custom_cases_from_request(request)
        submission = create_and_run_custom_submission(
            question,
            code,
            language,
            custom_cases,
            request.admin_api_user,
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(SubmissionSerializer(submission).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@admin_api_required
def submit_code(request, slug):
    question = get_object_or_404(Question, slug=slug, is_active=True)
    code = request.data.get("code", "")
    if not code.strip():
        return Response({"detail": "Code is required."}, status=status.HTTP_400_BAD_REQUEST)
    language = normalized_language(request.data.get("language"))
    if language is None:
        return Response({"detail": "Supported languages are java and python."}, status=status.HTTP_400_BAD_REQUEST)

    has_prior_submission = question.submissions.filter(user=request.admin_api_user, kind=Submission.Kind.SUBMIT).exists()
    solve_time_seconds = None if has_prior_submission else request.data.get("solve_time_seconds")
    if solve_time_seconds in ("", None):
        solve_time_seconds = None
    else:
        try:
            solve_time_seconds = max(0, int(solve_time_seconds))
        except (TypeError, ValueError):
            return Response({"detail": "solve_time_seconds must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

    submission = create_and_run_submission(
        question,
        code,
        language,
        sample_only=False,
        kind=Submission.Kind.SUBMIT,
        user=request.admin_api_user,
        solve_time_seconds=solve_time_seconds,
    )
    if submission is None:
        return Response({"detail": "This question has no test cases."}, status=status.HTTP_400_BAD_REQUEST)
    return Response(SubmissionSerializer(submission).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@admin_api_required
def submission_list(request, slug):
    question = get_object_or_404(Question, slug=slug, is_active=True)
    serializer = SubmissionListSerializer(question.submissions.filter(user=request.admin_api_user, kind=Submission.Kind.SUBMIT), many=True)
    return Response(serializer.data)


@api_view(["GET"])
@admin_api_required
def submission_detail(request, pk):
    submission = get_object_or_404(
        Submission.objects.select_related("question", "user").prefetch_related("results__test_case"),
        pk=pk,
        user=request.admin_api_user,
    )
    serializer = SubmissionSerializer(submission)
    return Response(serializer.data)


@api_view(["GET"])
@admin_api_required
def revision_list(request):
    submissions = (
        Submission.objects.filter(
            user=request.admin_api_user,
            kind=Submission.Kind.SUBMIT,
            status=Submission.Status.ACCEPTED,
            marked_for_revision=True,
            question__is_active=True,
        )
        .select_related("question")
        .order_by("question__title", "-created_at")
    )
    serializer = RevisionSubmissionSerializer(submissions, many=True)
    return Response(serializer.data)


@api_view(["POST"])
@admin_api_required
def mark_question_for_revision(request, slug):
    question = get_object_or_404(Question, slug=slug, is_active=True)
    marked = bool(request.data.get("marked", True))
    accepted_submissions = question.submissions.filter(
        user=request.admin_api_user,
        kind=Submission.Kind.SUBMIT,
        status=Submission.Status.ACCEPTED,
    )

    if not marked:
        accepted_submissions.update(marked_for_revision=False)
        return Response({"revision_marked": False, "submission": None})

    latest_submission = accepted_submissions.order_by("-created_at", "-id").first()
    if latest_submission is None:
        return Response({"detail": "Solve this problem before marking it for revision."}, status=status.HTTP_400_BAD_REQUEST)

    accepted_submissions.exclude(pk=latest_submission.pk).update(marked_for_revision=False)
    latest_submission.marked_for_revision = True
    latest_submission.save(update_fields=["marked_for_revision"])
    return Response({"revision_marked": True, "submission": SubmissionListSerializer(latest_submission).data})
