import shutil
import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import AdminApiToken
from .models import Question
from .models import Submission
from .models import TestCase as QuestionTestCase


class FunctionModeSubmissionTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_user(
            username="staff",
            email="staff@example.com",
            password="Password1!",
            is_staff=True,
        )
        self.token = AdminApiToken.objects.create(user=self.admin_user)
        self.auth_headers = {"HTTP_AUTHORIZATION": f"Bearer {self.token.token}"}

    def api_get(self, name, kwargs=None):
        return self.client.get(reverse(name, kwargs=kwargs), **self.auth_headers)

    def api_post(self, name, data, kwargs=None):
        return self.client.post(reverse(name, kwargs=kwargs), data, content_type="application/json", **self.auth_headers)

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

        response = self.api_get("question-detail", kwargs={"slug": question.slug})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["execution_mode"], Question.ExecutionMode.FUNCTION)
        self.assertEqual(response.data["function_name"], "solve")
        self.assertFalse(response.data["has_reference_solution"])

    def test_reference_solution_endpoint_returns_saved_solutions(self):
        question = self.create_function_question()
        question.java_reference_solution = "class Solution { public int solve(int a, int b) { return a + b; } }"
        question.python_reference_solution = "def solve(a, b):\n    return a + b\n"
        question.save()

        detail_response = self.api_get("question-detail", kwargs={"slug": question.slug})
        solution_response = self.api_get("question-reference-solution", kwargs={"slug": question.slug})

        self.assertTrue(detail_response.data["has_reference_solution"])
        self.assertEqual(solution_response.status_code, 200)
        self.assertEqual(solution_response.data["java_reference_solution"], question.java_reference_solution)
        self.assertEqual(solution_response.data["python_reference_solution"], question.python_reference_solution)

    def test_reference_solution_endpoint_returns_404_when_empty(self):
        question = self.create_function_question()

        response = self.api_get("question-reference-solution", kwargs={"slug": question.slug})

        self.assertEqual(response.status_code, 404)

    def test_python_function_submission_runs_without_input_parsing(self):
        question = self.create_function_question()

        response = self.api_post(
            "submit-code",
            {
                "language": Submission.Language.PYTHON,
                "code": "def solve(a, b):\n    return a + b\n",
            },
            kwargs={"slug": question.slug},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], Submission.Status.ACCEPTED)
        self.assertEqual(response.data["passed_count"], 2)
        self.assertEqual(response.data["total_count"], 2)
        self.assertEqual(response.data["results"][0]["stdout"].strip(), "3")
        self.assertEqual(response.data["results"][0]["expected_output"], "3")

    def test_python_function_run_uses_sample_cases_only(self):
        question = self.create_function_question()

        response = self.api_post(
            "run-code",
            {
                "language": Submission.Language.PYTHON,
                "code": "def solve(a, b):\n    return a + b\n",
            },
            kwargs={"slug": question.slug},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], Submission.Status.ACCEPTED)
        self.assertEqual(response.data["passed_count"], 1)
        self.assertEqual(response.data["total_count"], 1)

    def test_python_function_wrong_return_is_wrong_answer(self):
        question = self.create_function_question()

        response = self.api_post(
            "submit-code",
            {
                "language": Submission.Language.PYTHON,
                "code": "def solve(a, b):\n    return a - b\n",
            },
            kwargs={"slug": question.slug},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], Submission.Status.WRONG_ANSWER)
        self.assertEqual(response.data["passed_count"], 0)

    def test_java_function_submission_runs_without_input_parsing(self):
        if not shutil.which(settings.JAVAC_EXECUTABLE) or not shutil.which(settings.JAVA_EXECUTABLE):
            self.skipTest("Java toolchain is not available.")
        question = self.create_function_question()

        response = self.api_post(
            "submit-code",
            {
                "language": Submission.Language.JAVA,
                "code": "class Solution { public int solve(int a, int b) { return a + b; } }",
            },
            kwargs={"slug": question.slug},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], Submission.Status.ACCEPTED)
        self.assertEqual(response.data["passed_count"], 2)
        self.assertEqual(response.data["total_count"], 2)

    def test_only_first_submission_records_solve_time(self):
        question = self.create_function_question()
        payload = {
            "language": Submission.Language.PYTHON,
            "code": "def solve(a, b):\n    return a + b\n",
        }

        first_response = self.api_post(
            "submit-code",
            {**payload, "solve_time_seconds": 125},
            kwargs={"slug": question.slug},
        )
        second_response = self.api_post(
            "submit-code",
            {**payload, "solve_time_seconds": 999},
            kwargs={"slug": question.slug},
        )

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 201)
        self.assertEqual(first_response.data["solve_time_seconds"], 125)
        self.assertIsNone(second_response.data["solve_time_seconds"])

    def test_submission_number_is_ordered_per_problem(self):
        question = self.create_function_question()
        other_question = Question.objects.create(
            title="Other",
            slug="other-function",
            description="Other.",
            execution_mode=Question.ExecutionMode.FUNCTION,
            function_name="solve",
        )
        payload = {
            "language": Submission.Language.PYTHON,
            "code": "def solve(a, b):\n    return a + b\n",
        }

        first_response = self.api_post("submit-code", payload, kwargs={"slug": question.slug})
        self.api_post("submit-code", payload, kwargs={"slug": other_question.slug})
        second_response = self.api_post("submit-code", payload, kwargs={"slug": question.slug})
        list_response = self.api_get("submission-list", kwargs={"slug": question.slug})
        detail_response = self.api_get("submission-detail", kwargs={"pk": second_response.data["id"]})

        self.assertEqual(first_response.data["submission_number"], 1)
        self.assertEqual(second_response.data["submission_number"], 2)
        self.assertEqual(detail_response.data["submission_number"], 2)
        self.assertEqual([item["submission_number"] for item in list_response.data], [2, 1])

    def test_question_api_requires_admin_token(self):
        self.create_function_question()

        response = self.client.get(reverse("question-list"))

        self.assertEqual(response.status_code, 401)

    def test_non_staff_user_cannot_login_to_code_api(self):
        get_user_model().objects.create_user(
            username="regular",
            email="regular@example.com",
            password="Password1!",
        )

        response = self.client.post(
            reverse("auth-login"),
            {"username": "regular", "password": "Password1!"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_submission_history_is_scoped_to_authenticated_user(self):
        question = self.create_function_question()
        other_user = get_user_model().objects.create_user(
            username="other-staff",
            email="other-staff@example.com",
            password="Password1!",
            is_staff=True,
        )
        other_token = AdminApiToken.objects.create(user=other_user)
        payload = {
            "language": Submission.Language.PYTHON,
            "code": "def solve(a, b):\n    return a + b\n",
        }

        own_response = self.api_post("submit-code", payload, kwargs={"slug": question.slug})
        self.client.post(
            reverse("submit-code", kwargs={"slug": question.slug}),
            payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {other_token.token}",
        )
        list_response = self.api_get("submission-list", kwargs={"slug": question.slug})

        self.assertEqual([item["id"] for item in list_response.data], [own_response.data["id"]])


class QuestionAdminJsonImportTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="Password1!",
        )
        self.client.force_login(self.admin_user)

    def payload(self, slug="sum-two-values"):
        return {
            "question": {
                "title": "Sum Two Values",
                "slug": slug,
                "description": "Return the sum of two integers.\n\nFunction signature: solve(a, b)",
                "difficulty": "easy",
                "execution_mode": "function",
                "function_name": "solve",
                "is_active": True,
                "starter_code": "class Solution { public int solve(int a, int b) { return 0; } }",
                "java_starter_code": "class Solution { public int solve(int a, int b) { return 0; } }",
                "python_starter_code": "def solve(a, b):\n    return 0\n",
                "java_reference_solution": "class Solution { public int solve(int a, int b) { return a + b; } }",
                "python_reference_solution": "def solve(a, b):\n    return a + b\n",
            },
            "test_cases": [
                {
                    "name": "Sample 1",
                    "stdin": "",
                    "function_args": [1, 2],
                    "expected_value": 3,
                    "expected_output": "3",
                    "is_sample": True,
                    "is_hidden": False,
                    "order": 1,
                },
                {
                    "name": "Hidden 1",
                    "stdin": "",
                    "function_args": [-5, 7],
                    "expected_value": 2,
                    "expected_output": "2",
                    "is_sample": False,
                    "is_hidden": True,
                    "order": 2,
                },
            ],
        }

    def test_admin_can_import_question_json_with_test_cases(self):
        response = self.client.post(
            reverse("admin:core_question_import_json"),
            {
                "json_text": json.dumps(self.payload()),
            },
            follow=True,
        )

        question = Question.objects.get(slug="sum-two-values")
        self.assertEqual(response.redirect_chain[0][0], f"../{question.pk}/change/")
        self.assertEqual(question.execution_mode, Question.ExecutionMode.FUNCTION)
        self.assertEqual(question.function_name, "solve")
        self.assertIn("return a + b", question.java_reference_solution)
        self.assertIn("return a + b", question.python_reference_solution)
        self.assertEqual(question.test_cases.count(), 2)
        self.assertEqual(question.test_cases.get(name="Sample 1").function_args, [1, 2])
        self.assertContains(response, "Created question and imported 2 test cases.")

    def test_admin_import_requires_replace_for_duplicate_slug(self):
        Question.objects.create(
            title="Existing",
            slug="sum-two-values",
            description="Existing question.",
        )

        response = self.client.post(
            reverse("admin:core_question_import_json"),
            {
                "json_text": json.dumps(self.payload()),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A question with this slug already exists.")
        self.assertEqual(Question.objects.get(slug="sum-two-values").title, "Existing")

    def test_admin_can_replace_existing_question_from_json(self):
        question = Question.objects.create(
            title="Existing",
            slug="sum-two-values",
            description="Existing question.",
        )
        QuestionTestCase.objects.create(
            question=question,
            name="Old",
            expected_output="0",
            order=1,
        )

        response = self.client.post(
            reverse("admin:core_question_import_json"),
            {
                "json_text": json.dumps(self.payload()),
                "replace_existing": "on",
            },
            follow=True,
        )

        question.refresh_from_db()
        self.assertEqual(response.redirect_chain[0][0], f"../{question.pk}/change/")
        self.assertEqual(question.title, "Sum Two Values")
        self.assertEqual(question.test_cases.count(), 2)
        self.assertFalse(question.test_cases.filter(name="Old").exists())
