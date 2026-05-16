from rest_framework import serializers

from .models import Question, Submission, TestCaseResult


class QuestionListSerializer(serializers.ModelSerializer):
    solved = serializers.BooleanField()
    test_case_count = serializers.IntegerField()

    class Meta:
        model = Question
        fields = ["id", "title", "slug", "difficulty", "solved", "test_case_count"]


class QuestionDetailSerializer(serializers.ModelSerializer):
    solved = serializers.BooleanField()

    class Meta:
        model = Question
        fields = ["id", "title", "slug", "description", "difficulty", "starter_code", "solved"]


class TestCaseResultSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="test_case.name")
    is_sample = serializers.BooleanField(source="test_case.is_sample")
    is_hidden = serializers.BooleanField(source="test_case.is_hidden")

    class Meta:
        model = TestCaseResult
        fields = ["id", "name", "is_sample", "is_hidden", "status", "stdout", "stderr", "expected_output", "execution_time_ms"]


class SubmissionSerializer(serializers.ModelSerializer):
    results = TestCaseResultSerializer(many=True, read_only=True)

    class Meta:
        model = Submission
        fields = [
            "id",
            "question",
            "kind",
            "code",
            "status",
            "stdout",
            "stderr",
            "execution_time_ms",
            "solve_time_seconds",
            "passed_count",
            "total_count",
            "created_at",
            "results",
        ]


class SubmissionListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Submission
        fields = ["id", "kind", "status", "execution_time_ms", "solve_time_seconds", "passed_count", "total_count", "created_at"]
