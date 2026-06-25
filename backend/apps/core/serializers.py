from rest_framework import serializers

from .models import Question, Submission, TestCaseResult


class QuestionListSerializer(serializers.ModelSerializer):
    solved = serializers.BooleanField()
    revision_marked = serializers.BooleanField()
    test_case_count = serializers.IntegerField()

    class Meta:
        model = Question
        fields = ["id", "title", "slug", "difficulty", "solved", "revision_marked", "test_case_count"]


class QuestionDetailSerializer(serializers.ModelSerializer):
    solved = serializers.BooleanField()
    revision_marked = serializers.BooleanField()
    has_reference_solution = serializers.SerializerMethodField()

    def get_has_reference_solution(self, obj):
        return bool(obj.java_reference_solution.strip() or obj.python_reference_solution.strip())

    class Meta:
        model = Question
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "difficulty",
            "starter_code",
            "java_starter_code",
            "python_starter_code",
            "execution_mode",
            "function_name",
            "solved",
            "revision_marked",
            "has_reference_solution",
        ]


class QuestionReferenceSolutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ["id", "title", "slug", "java_reference_solution", "python_reference_solution"]


class TestCaseResultSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    is_sample = serializers.SerializerMethodField()
    is_hidden = serializers.SerializerMethodField()

    def get_name(self, obj):
        if obj.test_case_id:
            return obj.test_case.name
        return obj.custom_name

    def get_is_sample(self, obj):
        return bool(obj.test_case and obj.test_case.is_sample)

    def get_is_hidden(self, obj):
        return bool(obj.test_case and obj.test_case.is_hidden)

    class Meta:
        model = TestCaseResult
        fields = ["id", "name", "is_sample", "is_hidden", "status", "stdout", "stderr", "expected_output", "execution_time_ms", "memory_kb", "custom_input"]


class SubmissionSerializer(serializers.ModelSerializer):
    results = TestCaseResultSerializer(many=True, read_only=True)
    question_slug = serializers.CharField(source="question.slug", read_only=True)
    question_title = serializers.CharField(source="question.title", read_only=True)
    submission_number = serializers.SerializerMethodField()

    def get_submission_number(self, obj):
        if obj.kind != Submission.Kind.SUBMIT:
            return None
        return (
            Submission.objects.filter(
                question=obj.question,
                user=obj.user,
                kind=Submission.Kind.SUBMIT,
                created_at__lt=obj.created_at,
            ).count()
            + Submission.objects.filter(
                question=obj.question,
                user=obj.user,
                kind=Submission.Kind.SUBMIT,
                created_at=obj.created_at,
                id__lte=obj.id,
            ).count()
        )

    class Meta:
        model = Submission
        fields = [
            "id",
            "question",
            "question_slug",
            "question_title",
            "submission_number",
            "kind",
            "language",
            "code",
            "status",
            "stdout",
            "stderr",
            "execution_time_ms",
            "memory_kb",
            "solve_time_seconds",
            "marked_for_revision",
            "passed_count",
            "total_count",
            "created_at",
            "results",
        ]


class SubmissionListSerializer(serializers.ModelSerializer):
    submission_number = serializers.SerializerMethodField()

    def get_submission_number(self, obj):
        if obj.kind != Submission.Kind.SUBMIT:
            return None
        return (
            Submission.objects.filter(
                question=obj.question,
                user=obj.user,
                kind=Submission.Kind.SUBMIT,
                created_at__lt=obj.created_at,
            ).count()
            + Submission.objects.filter(
                question=obj.question,
                user=obj.user,
                kind=Submission.Kind.SUBMIT,
                created_at=obj.created_at,
                id__lte=obj.id,
            ).count()
        )

    class Meta:
        model = Submission
        fields = [
            "id",
            "submission_number",
            "kind",
            "language",
            "status",
            "execution_time_ms",
            "memory_kb",
            "solve_time_seconds",
            "marked_for_revision",
            "passed_count",
            "total_count",
            "created_at",
        ]


class RevisionSubmissionSerializer(serializers.ModelSerializer):
    question_slug = serializers.CharField(source="question.slug", read_only=True)
    question_title = serializers.CharField(source="question.title", read_only=True)

    class Meta:
        model = Submission
        fields = [
            "id",
            "question_slug",
            "question_title",
            "language",
            "code",
            "execution_time_ms",
            "memory_kb",
            "created_at",
        ]
