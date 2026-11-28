import shutil
import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.product.models import UserFeatureFlags

from .models import AdminApiToken
from .models import InterviewRoom
from .models import Question
from .models import Submission
from .models import TestCase as QuestionTestCase
from .models import Track, TrackQuestion


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
        self.assertIn("memory_kb", response.data)
        self.assertIn("memory_kb", response.data["results"][0])
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

    def test_python_function_custom_run_uses_custom_json_arguments(self):
        question = self.create_function_question()

        response = self.api_post(
            "run-custom-code",
            {
                "language": Submission.Language.PYTHON,
                "code": "def solve(a, b):\n    return a + b\n",
                "input": "[7, 8]",
                "expected_output": "15",
            },
            kwargs={"slug": question.slug},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["kind"], Submission.Kind.CUSTOM)
        self.assertEqual(response.data["status"], Submission.Status.ACCEPTED)
        self.assertEqual(response.data["passed_count"], 1)
        self.assertEqual(response.data["total_count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "Custom test 1")
        self.assertEqual(response.data["results"][0]["custom_input"], "[7, 8]")
        self.assertEqual(response.data["results"][0]["stdout"].strip(), "15")

    def test_custom_run_does_not_require_expected_output(self):
        question = self.create_function_question()

        response = self.api_post(
            "run-custom-code",
            {
                "language": Submission.Language.PYTHON,
                "code": "def solve(a, b):\n    return a + b\n",
                "input": "[7, 8]",
            },
            kwargs={"slug": question.slug},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["kind"], Submission.Kind.CUSTOM)
        self.assertEqual(response.data["status"], Submission.Status.ACCEPTED)
        self.assertEqual(response.data["passed_count"], 0)
        self.assertEqual(response.data["total_count"], 1)
        self.assertEqual(response.data["results"][0]["expected_output"], "")
        self.assertEqual(response.data["results"][0]["stdout"].strip(), "15")

    def test_custom_run_accepts_multiple_test_cases(self):
        question = self.create_function_question()

        response = self.api_post(
            "run-custom-code",
            {
                "language": Submission.Language.PYTHON,
                "code": "def solve(a, b):\n    return a + b\n",
                "test_cases": [
                    {"input": "[1, 2]", "expected_output": "3"},
                    {"input": "[7, 8]"},
                ],
            },
            kwargs={"slug": question.slug},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["total_count"], 2)
        self.assertEqual([item["name"] for item in response.data["results"]], ["Custom test 1", "Custom test 2"])
        self.assertEqual(response.data["passed_count"], 1)
        self.assertEqual(response.data["results"][1]["expected_output"], "")
        self.assertEqual(response.data["results"][1]["stdout"].strip(), "15")

    def test_custom_run_allows_up_to_five_test_cases(self):
        question = self.create_function_question()

        response = self.api_post(
            "run-custom-code",
            {
                "language": Submission.Language.PYTHON,
                "code": "def solve(a, b):\n    return a + b\n",
                "test_cases": [{"input": "[1, 2]"} for _ in range(6)],
            },
            kwargs={"slug": question.slug},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("up to 5", response.data["detail"])

    def test_custom_function_run_requires_json_input(self):
        question = self.create_function_question()

        response = self.api_post(
            "run-custom-code",
            {
                "language": Submission.Language.PYTHON,
                "code": "def solve(a, b):\n    return a + b\n",
                "input": "7 8",
                "expected_output": "15",
            },
            kwargs={"slug": question.slug},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("valid JSON", response.data["detail"])

    def test_stdin_custom_run_uses_custom_input_and_expected_output(self):
        question = Question.objects.create(
            title="Echo",
            slug="echo",
            description="Echo input.",
            execution_mode=Question.ExecutionMode.STDIN,
        )

        response = self.api_post(
            "run-custom-code",
            {
                "language": Submission.Language.PYTHON,
                "code": "print(input()[::-1])\n",
                "input": "abc\n",
                "expected_output": "cba",
            },
            kwargs={"slug": question.slug},
        )
        list_response = self.api_get("submission-list", kwargs={"slug": question.slug})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["kind"], Submission.Kind.CUSTOM)
        self.assertEqual(response.data["status"], Submission.Status.ACCEPTED)
        self.assertEqual(response.data["results"][0]["custom_input"], "abc\n")
        self.assertEqual(list_response.data, [])

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

    def test_mark_revision_uses_latest_accepted_submission(self):
        question = self.create_function_question()
        first_response = self.api_post(
            "submit-code",
            {
                "language": Submission.Language.PYTHON,
                "code": "def solve(a, b):\n    return a + b\n",
            },
            kwargs={"slug": question.slug},
        )
        second_response = self.api_post(
            "submit-code",
            {
                "language": Submission.Language.PYTHON,
                "code": "def solve(a, b):\n    return a + b\n# latest\n",
            },
            kwargs={"slug": question.slug},
        )

        mark_response = self.api_post("mark-question-revision", {"marked": True}, kwargs={"slug": question.slug})
        revision_response = self.api_get("revision-list")
        detail_response = self.api_get("question-detail", kwargs={"slug": question.slug})

        self.assertEqual(mark_response.status_code, 200)
        self.assertTrue(mark_response.data["revision_marked"])
        self.assertEqual(mark_response.data["submission"]["id"], second_response.data["id"])
        self.assertFalse(Submission.objects.get(pk=first_response.data["id"]).marked_for_revision)
        self.assertTrue(Submission.objects.get(pk=second_response.data["id"]).marked_for_revision)
        self.assertTrue(detail_response.data["revision_marked"])
        self.assertEqual(len(revision_response.data), 1)
        self.assertEqual(revision_response.data[0]["id"], second_response.data["id"])

    def test_unsolved_question_cannot_be_marked_for_revision(self):
        question = self.create_function_question()

        response = self.api_post("mark-question-revision", {"marked": True}, kwargs={"slug": question.slug})

        self.assertEqual(response.status_code, 400)

    def test_track_revision_automatically_lists_latest_accepted_solutions(self):
        solved_question = self.create_function_question()
        outside_question = Question.objects.create(title="Outside", slug="outside", description="Outside")
        track = Track.objects.get(slug="interview-preparation")
        section = track.sections.order_by("order").first()
        self.assertIsNotNone(section)
        TrackQuestion.objects.create(section=section, question=solved_question, order=1)

        payload = {"language": Submission.Language.PYTHON, "code": "def solve(a, b):\n    return a + b\n"}
        first = self.api_post("submit-code", payload, kwargs={"slug": solved_question.slug})
        latest = self.api_post(
            "submit-code",
            {**payload, "code": payload["code"] + "# latest\n"},
            kwargs={"slug": solved_question.slug},
        )
        Submission.objects.create(
            user=self.admin_user,
            question=outside_question,
            kind=Submission.Kind.SUBMIT,
            language=Submission.Language.PYTHON,
            code="outside",
            status=Submission.Status.ACCEPTED,
        )

        response = self.api_get("track-revision-list", kwargs={"slug": track.slug})

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data], [latest.data["id"]])
        self.assertNotEqual(response.data[0]["id"], first.data["id"])
        self.assertFalse(Submission.objects.get(pk=latest.data["id"]).marked_for_revision)

    def test_question_api_requires_admin_token(self):
        self.create_function_question()

        response = self.client.get(reverse("question-list"))

        self.assertEqual(response.status_code, 401)

    def test_non_staff_user_without_coding_access_cannot_login_to_code_api(self):
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
        self.assertEqual(response.data["detail"], "Coding platform access is required.")

    def test_non_staff_user_with_coding_access_can_login_to_code_api(self):
        user = get_user_model().objects.create_user(
            username="coder",
            email="coder@example.com",
            password="Password1!",
        )
        UserFeatureFlags.objects.create(user=user, can_access_coding_platform=True)

        response = self.client.post(
            reverse("auth-login"),
            {"username": "coder", "password": "Password1!"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)
        self.assertFalse(response.data["user"]["is_staff"])
        self.assertTrue(response.data["user"]["can_access_coding_platform"])

    def test_non_staff_token_with_coding_access_can_use_question_api(self):
        question = self.create_function_question()
        user = get_user_model().objects.create_user(
            username="coder-token",
            email="coder-token@example.com",
            password="Password1!",
        )
        UserFeatureFlags.objects.create(user=user, can_access_coding_platform=True)
        token = AdminApiToken.objects.create(user=user)

        response = self.client.get(reverse("question-detail", kwargs={"slug": question.slug}), HTTP_AUTHORIZATION=f"Bearer {token.token}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["slug"], question.slug)

    def test_non_staff_token_without_coding_access_cannot_use_question_api(self):
        question = self.create_function_question()
        user = get_user_model().objects.create_user(
            username="blocked-token",
            email="blocked-token@example.com",
            password="Password1!",
        )
        token = AdminApiToken.objects.create(user=user)

        response = self.client.get(reverse("question-detail", kwargs={"slug": question.slug}), HTTP_AUTHORIZATION=f"Bearer {token.token}")

        self.assertEqual(response.status_code, 401)

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


class ScratchpadApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="scratch", password="Password1!")
        UserFeatureFlags.objects.create(user=self.user, can_access_coding_platform=True)
        self.token = AdminApiToken.objects.create(user=self.user)
        self.auth_headers = {"HTTP_AUTHORIZATION": f"Bearer {self.token.token}"}

    def api(self, method, name, data=None):
        return getattr(self.client, method)(reverse(name), data=json.dumps(data) if data is not None else None,
                                           content_type="application/json", **self.auth_headers)

    def test_draft_round_trips_both_languages_for_user(self):
        payload = {"java_code": "class Main {}", "python_code": "print(1)", "selected_language": "java"}
        saved = self.api("put", "scratchpad-draft", payload)
        loaded = self.api("get", "scratchpad-draft")
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(loaded.data["java_code"], payload["java_code"])
        self.assertEqual(loaded.data["python_code"], payload["python_code"])
        self.assertEqual(loaded.data["selected_language"], "java")

    def test_run_executes_python_and_returns_output(self):
        response = self.api("post", "scratchpad-run", {"language": "python", "code": "print(42)", "input": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["stdout"], "42\n")
        self.assertEqual(response.data["status"], "completed")

    def test_run_compiles_and_executes_java(self):
        code = 'public class Main { public static void main(String[] args) { System.out.println("42"); } }'
        response = self.api("post", "scratchpad-run", {"language": "java", "code": code, "input": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["stdout"], "42\n")
        self.assertEqual(response.data["status"], "completed")

    def test_run_requires_coding_authentication(self):
        response = self.client.post(reverse("scratchpad-run"), data=json.dumps({"language": "python", "code": "print(1)"}), content_type="application/json")
        self.assertEqual(response.status_code, 401)


class InterviewRoomApiTests(TestCase):
    def setUp(self):
        self.interviewer = get_user_model().objects.create_user(
            username="interviewer", email="host@company.example", password="Password1!", first_name="Taylor",
        )
        UserFeatureFlags.objects.create(user=self.interviewer, can_access_coding_platform=True)
        self.token = AdminApiToken.objects.create(user=self.interviewer)
        self.auth_headers = {"HTTP_AUTHORIZATION": f"Bearer {self.token.token}"}

    def host(self, data=None, room_uuid=None, action="create"):
        if action == "create":
            return self.client.post(reverse("interview-room-create"), data=json.dumps(data or {}), content_type="application/json", **self.auth_headers)
        name = "interview-room-close" if action == "close" else "interview-room-detail"
        kwargs = {"room_uuid": room_uuid}
        method = "post" if action == "close" else "get"
        return getattr(self.client, method)(reverse(name, kwargs=kwargs), data=json.dumps(data or {}) if method == "post" else None,
                                           content_type="application/json", **self.auth_headers)

    def public(self, method, room_uuid, data=None, action="detail"):
        name = "interview-room-run" if action == "run" else "interview-room-detail"
        path = reverse(name, kwargs={"room_uuid": room_uuid})
        return getattr(self.client, method)(path, data=json.dumps(data or {}) if data is not None else None,
                                            content_type="application/json")

    def test_corporate_interviewer_creates_private_room_and_candidate_joins(self):
        response = self.host({"title": "Pairing", "problem_statement": "Sum two integers.", "language": "python"})
        room_uuid = response.data["id"]
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["role"], "interviewer")
        self.assertIn("def solve", response.data["code"])

        guest_view = self.public("get", room_uuid)
        self.assertEqual(guest_view.status_code, 200)
        self.assertEqual(guest_view.data["role"], "candidate")
        self.assertFalse(guest_view.data["candidate_joined"])

        joined = self.public("patch", room_uuid, {"candidate_name": "Sam", "candidate_email": "Sam@Example.org", "code": 'print("hello")'})
        self.assertEqual(joined.status_code, 200)
        self.assertTrue(joined.data["candidate_joined"])
        self.assertEqual(joined.data["candidate_name"], "Sam")
        self.assertEqual(joined.data["candidate_email"], "sam@example.org")

        host_view = self.host(room_uuid=room_uuid, action="detail")
        self.assertEqual(host_view.data["role"], "interviewer")
        self.assertEqual(host_view.data["code"], 'print("hello")')

    def test_personal_email_cannot_host(self):
        self.interviewer.email = "host@gmail.com"
        self.interviewer.save(update_fields=("email",))
        response = self.host({"title": "Pairing"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(InterviewRoom.objects.exists())

    def test_superuser_can_host_and_manage_room_with_personal_email(self):
        superuser = get_user_model().objects.create_superuser(
            username="root", email="root@gmail.com", password="Password1!",
        )
        token = AdminApiToken.objects.create(user=superuser)
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token.token}"}
        create = self.client.post(
            reverse("interview-room-create"), data=json.dumps({"title": "Admin interview"}),
            content_type="application/json", **headers,
        )
        room_uuid = create.data["id"]
        view = self.client.get(reverse("interview-room-detail", kwargs={"room_uuid": room_uuid}), **headers)
        close = self.client.post(reverse("interview-room-close", kwargs={"room_uuid": room_uuid}), data="{}",
                                 content_type="application/json", **headers)
        self.assertEqual(create.status_code, 201)
        self.assertEqual(view.data["role"], "interviewer")
        self.assertEqual(close.status_code, 200)
        self.assertTrue(close.data["is_closed"])

    def test_candidate_can_run_code_after_joining(self):
        room = InterviewRoom.objects.create(interviewer=self.interviewer, language="python", code='print("42")')
        before_join = self.public("post", room.uuid, action="run")
        self.assertEqual(before_join.status_code, 409)
        self.public("patch", room.uuid, {"candidate_name": "Sam", "candidate_email": "sam@example.org"})
        response = self.public("post", room.uuid, action="run")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["stdout"], "42\n")
        self.assertEqual(response.data["status"], "completed")

    def test_closed_interview_review_is_limited_to_interviewer_and_invited_hr(self):
        room = InterviewRoom.objects.create(
            interviewer=self.interviewer, candidate_name="Sam", candidate_email="sam@example.org",
            candidate_joined_at=timezone.now(), code='print("review")', is_closed=True,
        )
        candidate = get_user_model().objects.create_user(
            username="candidate", email="sam@example.org", password="Password1!",
        )
        UserFeatureFlags.objects.create(user=candidate, can_access_coding_platform=True)
        candidate_token = AdminApiToken.objects.create(user=candidate)
        candidate_headers = {"HTTP_AUTHORIZATION": f"Bearer {candidate_token.token}"}
        denied_candidate = self.client.get(
            reverse("interview-room-detail", kwargs={"room_uuid": room.uuid}), **candidate_headers,
        )
        self.assertEqual(denied_candidate.status_code, 410)

        candidate_share = self.client.post(
            reverse("interview-room-share", kwargs={"room_uuid": room.uuid}),
            data=json.dumps({"email": "sam@example.org"}), content_type="application/json", **self.auth_headers,
        )
        self.assertEqual(candidate_share.status_code, 400)

        share = self.client.post(
            reverse("interview-room-share", kwargs={"room_uuid": room.uuid}),
            data=json.dumps({"email": "hr@company.example"}), content_type="application/json", **self.auth_headers,
        )
        self.assertEqual(share.status_code, 200)
        self.assertEqual(share.data["hr_share_emails"], ["hr@company.example"])

        hr = get_user_model().objects.create_user(
            username="hr", email="HR@company.example", password="Password1!",
        )
        UserFeatureFlags.objects.create(user=hr, can_access_coding_platform=True)
        hr_token = AdminApiToken.objects.create(user=hr)
        hr_view = self.client.get(
            reverse("interview-room-detail", kwargs={"room_uuid": room.uuid}),
            HTTP_AUTHORIZATION=f"Bearer {hr_token.token}",
        )
        interviewer_view = self.host(room_uuid=room.uuid, action="detail")
        self.assertEqual(hr_view.status_code, 200)
        self.assertEqual(hr_view.data["role"], "reviewer")
        self.assertEqual(hr_view.data["code"], 'print("review")')
        self.assertEqual(interviewer_view.status_code, 200)

    def test_candidate_cannot_change_interviewer_problem_statement(self):
        room = InterviewRoom.objects.create(interviewer=self.interviewer, problem_statement="Original prompt")
        self.public("patch", room.uuid, {"candidate_name": "Sam", "candidate_email": "sam@example.org"})
        response = self.public("patch", room.uuid, {"problem_statement": "Changed prompt"})
        room.refresh_from_db()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(room.problem_statement, "Original prompt")

    def test_candidate_must_provide_a_valid_email_to_join(self):
        room = InterviewRoom.objects.create(interviewer=self.interviewer)
        missing = self.public("patch", room.uuid, {"candidate_name": "Sam"})
        invalid = self.public("patch", room.uuid, {"candidate_name": "Sam", "candidate_email": "not-an-email"})
        room.refresh_from_db()
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(invalid.status_code, 400)
        self.assertFalse(room.candidate_joined_at)
        self.assertEqual(room.candidate_email, "")

    def test_existing_joined_candidate_can_add_missing_email(self):
        room = InterviewRoom.objects.create(
            interviewer=self.interviewer, candidate_name="Sam", candidate_joined_at=timezone.now(),
        )
        response = self.public("patch", room.uuid, {"candidate_name": "Sam", "candidate_email": "sam@example.org"})
        room.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(room.candidate_email, "sam@example.org")

    def test_anonymous_user_cannot_create_or_close_rooms(self):
        create = self.client.post(reverse("interview-room-create"), data="{}", content_type="application/json")
        room = InterviewRoom.objects.create(interviewer=self.interviewer)
        close = self.client.post(reverse("interview-room-close", kwargs={"room_uuid": room.uuid}), data="{}", content_type="application/json")
        self.assertEqual(create.status_code, 401)
        self.assertEqual(close.status_code, 401)


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


class HealthTests(TestCase):
    def test_anonymous_health_request_returns_heartbeat(self):
        response = self.client.get(reverse("health"), HTTP_ACCEPT="application/json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
