from django.core.management import call_command
from django.test import TestCase

from .executor import run_submission
from .interview_node_questions import JAVA_RETURN_TYPES, LINKED_LIST_TITLES, NODE_TITLES, PYTHON_RETURN_TYPES
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
                self.assertIn(f"public {JAVA_RETURN_TYPES[question.title]} solve(", question.java_starter_code)
                self.assertIn(f") -> {PYTHON_RETURN_TYPES[question.title]}:", question.python_starter_code)
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

    def test_tree_run_and_submit_convert_arrays_without_user_defined_tree_node(self):
        question = Question.objects.get(title="Maximum Depth of Binary Tree")
        code = """def solve(root):
    def depth(node):
        if node is None:
            return 0
        return 1 + max(depth(node.left), depth(node.right))
    return depth(root)
"""

        self.assert_run_and_submit_accepted(question, code)

    def test_linked_list_run_and_submit_convert_arrays_without_user_defined_list_node(self):
        question = Question.objects.get(title="Reverse Linked List")
        code = """def solve(head):
    previous = None
    while head is not None:
        next_node = head.next
        head.next = previous
        previous = head
        head = next_node
    return previous
"""

        self.assert_run_and_submit_accepted(question, code)

    def assert_run_and_submit_accepted(self, question, code):
        for kind, test_cases, expected_count in (
            (Submission.Kind.RUN, question.test_cases.filter(is_sample=True), 2),
            (Submission.Kind.SUBMIT, question.test_cases.all(), 10),
        ):
            with self.subTest(question=question.slug, kind=kind):
                submission = Submission.objects.create(
                    question=question,
                    language=Submission.Language.PYTHON,
                    code=code,
                    kind=kind,
                )
                run_submission(submission, test_cases)
                submission.refresh_from_db()
                self.assertEqual(
                    submission.status,
                    Submission.Status.ACCEPTED,
                    submission.stderr or submission.stdout,
                )
                self.assertEqual(submission.passed_count, expected_count)
                self.assertEqual(submission.total_count, expected_count)

    def test_lru_cache_keeps_operation_based_signature(self):
        question = Question.objects.get(title="LRU Cache")

        self.assertNotIn(question.title, NODE_TITLES)
        self.assertNotIn("ListNode", question.java_starter_code)
        self.assertNotIn("TreeNode", question.java_starter_code)
