from django.core.management import call_command
from django.test import TestCase

from .executor import run_submission
from .interview_node_questions import LINKED_LIST_TITLES, NODE_TITLES
from .models import Question, Submission


class InterviewNodeQuestionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_interview_track", create_missing=True, verbosity=0)

    def test_node_questions_have_real_node_starters_and_ten_cases(self):
        questions = Question.objects.filter(title__in=NODE_TITLES)

        self.assertEqual(questions.count(), len(NODE_TITLES))
        for question in questions:
            with self.subTest(question=question.slug):
                node_type = "ListNode" if question.title in LINKED_LIST_TITLES else "TreeNode"
                self.assertIn(f"class {node_type}", question.java_starter_code)
                self.assertIn(f"class {node_type}", question.python_starter_code)
                parameter_name = "head" if question.title in LINKED_LIST_TITLES else "root"
                self.assertIn(f"{node_type} {parameter_name}", question.java_starter_code)
                self.assertIn(f"{parameter_name}: {node_type}", question.python_starter_code)
                self.assertEqual(question.test_cases.count(), 10)
                self.assertEqual(question.test_cases.filter(is_sample=True, is_hidden=False).count(), 2)
                self.assertEqual(question.test_cases.filter(is_sample=False, is_hidden=True).count(), 8)

    def test_all_node_reference_solutions_pass_all_cases(self):
        questions = Question.objects.filter(title__in=NODE_TITLES).order_by("title")

        for question in questions:
            for language, code in (
                (Submission.Language.JAVA, question.java_reference_solution),
                (Submission.Language.PYTHON, question.python_reference_solution),
            ):
                with self.subTest(question=question.slug, language=language):
                    submission = Submission.objects.create(
                        question=question,
                        language=language,
                        code=code,
                    )
                    run_submission(submission, question.test_cases.all())
                    submission.refresh_from_db()
                    self.assertEqual(
                        submission.status,
                        Submission.Status.ACCEPTED,
                        submission.stderr or submission.stdout,
                    )
                    self.assertEqual(submission.passed_count, 10)

    def test_lru_cache_keeps_operation_based_signature(self):
        question = Question.objects.get(title="LRU Cache")

        self.assertNotIn(question.title, NODE_TITLES)
        self.assertNotIn("ListNode", question.java_starter_code)
        self.assertNotIn("TreeNode", question.java_starter_code)
