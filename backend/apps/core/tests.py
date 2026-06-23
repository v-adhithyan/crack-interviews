import shutil

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from .models import Question
from .models import Submission
from .models import TestCase as QuestionTestCase


class FunctionModeSubmissionTests(TestCase):
    def create_function_question(self):
        question = Question.objects.create(
            title="Add Two Numbers",
            slug="function-add-two-numbers",
            description="Return a + b.",
            execution_mode=Question.ExecutionMode.FUNCTION,
            function_name="solve",
            java_starter_code="class Solution { public int solve(int a, int b) { return a + b; } }",
            python_starter_code="def solve(a, b):\n    return a + b\n",
        )
        QuestionTestCase.objects.create(
            question=question,
            name="Sample 1",
            function_args=[1, 2],
            expected_value=3,
            expected_output="3",
            is_sample=True,
            is_hidden=False,
            order=1,
        )
        QuestionTestCase.objects.create(
            question=question,
            name="Hidden 1",
            function_args=[10, 25],
            expected_value=35,
            expected_output="35",
            is_sample=False,
            is_hidden=True,
            order=2,
        )
        return question

    def test_question_detail_exposes_function_mode_metadata(self):
        question = self.create_function_question()

        response = self.client.get(reverse("question-detail", kwargs={"slug": question.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["execution_mode"], Question.ExecutionMode.FUNCTION)
        self.assertEqual(response.data["function_name"], "solve")

    def test_python_function_submission_runs_without_input_parsing(self):
        question = self.create_function_question()

        response = self.client.post(
            reverse("submit-code", kwargs={"slug": question.slug}),
            {
                "language": Submission.Language.PYTHON,
                "code": "def solve(a, b):\n    return a + b\n",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], Submission.Status.ACCEPTED)
        self.assertEqual(response.data["passed_count"], 2)
        self.assertEqual(response.data["total_count"], 2)
        self.assertEqual(response.data["results"][0]["stdout"].strip(), "3")
        self.assertEqual(response.data["results"][0]["expected_output"], "3")

    def test_python_function_run_uses_sample_cases_only(self):
        question = self.create_function_question()

        response = self.client.post(
            reverse("run-code", kwargs={"slug": question.slug}),
            {
                "language": Submission.Language.PYTHON,
                "code": "def solve(a, b):\n    return a + b\n",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], Submission.Status.ACCEPTED)
        self.assertEqual(response.data["passed_count"], 1)
        self.assertEqual(response.data["total_count"], 1)

    def test_python_function_wrong_return_is_wrong_answer(self):
        question = self.create_function_question()

        response = self.client.post(
            reverse("submit-code", kwargs={"slug": question.slug}),
            {
                "language": Submission.Language.PYTHON,
                "code": "def solve(a, b):\n    return a - b\n",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], Submission.Status.WRONG_ANSWER)
        self.assertEqual(response.data["passed_count"], 0)

    def test_java_function_submission_runs_without_input_parsing(self):
        if not shutil.which(settings.JAVAC_EXECUTABLE) or not shutil.which(settings.JAVA_EXECUTABLE):
            self.skipTest("Java toolchain is not available.")
        question = self.create_function_question()

        response = self.client.post(
            reverse("submit-code", kwargs={"slug": question.slug}),
            {
                "language": Submission.Language.JAVA,
                "code": "class Solution { public int solve(int a, int b) { return a + b; } }",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], Submission.Status.ACCEPTED)
        self.assertEqual(response.data["passed_count"], 2)
        self.assertEqual(response.data["total_count"], 2)
