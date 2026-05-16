from django.db.models import Count, Exists, OuterRef
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .executor import run_submission
from .models import Question, Submission
from .serializers import (
    QuestionDetailSerializer,
    QuestionListSerializer,
    SubmissionListSerializer,
    SubmissionSerializer,
)


def questions_with_solved_flag():
    accepted = Submission.objects.filter(
        question=OuterRef("pk"),
        kind=Submission.Kind.SUBMIT,
        status=Submission.Status.ACCEPTED,
    )
    return (
        Question.objects.filter(is_active=True)
        .annotate(solved=Exists(accepted), test_case_count=Count("test_cases"))
        .order_by("title")
    )


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


@api_view(["GET"])
def question_list(request):
    serializer = QuestionListSerializer(questions_with_solved_flag(), many=True)
    return Response(serializer.data)


@api_view(["GET"])
def question_detail(request, slug):
    question = get_object_or_404(questions_with_solved_flag(), slug=slug)
    serializer = QuestionDetailSerializer(question)
    return Response(serializer.data)


def create_and_run_submission(question, code, sample_only, kind):
    test_cases = question.test_cases.all()
    if sample_only:
        test_cases = test_cases.filter(is_sample=True)
    if not test_cases.exists():
        return None

    submission = Submission.objects.create(question=question, code=code, kind=kind)
    return run_submission(submission, test_cases)


@api_view(["POST"])
def run_code(request, slug):
    question = get_object_or_404(Question, slug=slug, is_active=True)
    code = request.data.get("code", "")
    if not code.strip():
        return Response({"detail": "Code is required."}, status=status.HTTP_400_BAD_REQUEST)

    submission = create_and_run_submission(question, code, sample_only=True, kind=Submission.Kind.RUN)
    if submission is None:
        return Response({"detail": "This question has no sample test cases."}, status=status.HTTP_400_BAD_REQUEST)
    return Response(SubmissionSerializer(submission).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
def submit_code(request, slug):
    question = get_object_or_404(Question, slug=slug, is_active=True)
    code = request.data.get("code", "")
    if not code.strip():
        return Response({"detail": "Code is required."}, status=status.HTTP_400_BAD_REQUEST)

    submission = create_and_run_submission(question, code, sample_only=False, kind=Submission.Kind.SUBMIT)
    if submission is None:
        return Response({"detail": "This question has no test cases."}, status=status.HTTP_400_BAD_REQUEST)
    return Response(SubmissionSerializer(submission).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def submission_list(request, slug):
    question = get_object_or_404(Question, slug=slug, is_active=True)
    serializer = SubmissionListSerializer(question.submissions.filter(kind=Submission.Kind.SUBMIT), many=True)
    return Response(serializer.data)


@api_view(["GET"])
def submission_detail(request, pk):
    submission = get_object_or_404(Submission.objects.select_related("question").prefetch_related("results__test_case"), pk=pk)
    serializer = SubmissionSerializer(submission)
    return Response(serializer.data)
