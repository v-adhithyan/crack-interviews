from django.core.management import call_command
from django.test import TestCase

from .executor import run_submission, values_match
from .interview_unordered_questions import UNORDERED_COMPARISON_MODES
from .models import Question, Submission


class UnorderedOutputTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_interview_track", create_missing=True, verbosity=0)

    def test_group_anagrams_accepts_reordered_groups_and_members(self):
        question = Question.objects.get(title="Group Anagrams")

        self.assertEqual(question.comparison_mode, Question.ComparisonMode.UNORDERED_NESTED_LISTS)
        self.assertTrue(
            values_match(
                question,
                [["tan", "nat"], ["tea", "eat", "ate"], ["bat"]],
                [["bat"], ["nat", "tan"], ["ate", "eat", "tea"]],
            )
        )
        self.assertFalse(values_match(question, [["eat", "tea"], ["bat"]], [["eat", "tea", "ate"], ["bat"]]))

    def test_letter_combinations_accepts_reordered_results(self):
        question = Question.objects.get(title="Letter Combinations of a Phone Number")

        self.assertEqual(question.comparison_mode, Question.ComparisonMode.UNORDERED_LIST)
        self.assertTrue(values_match(question, ["cf", "ae", "bd"], ["bd", "cf", "ae"]))
        self.assertFalse(values_match(question, ["cf", "ae"], ["bd", "cf", "ae"]))

    def test_ordered_questions_still_require_exact_order(self):
        question = Question.objects.get(title="Two Sum")

        self.assertEqual(question.comparison_mode, Question.ComparisonMode.ORDERED)
        self.assertFalse(values_match(question, [1, 0], [0, 1]))

    def test_unordered_questions_have_ten_cases_and_passing_references(self):
        for title in UNORDERED_COMPARISON_MODES:
            question = Question.objects.get(title=title)
            with self.subTest(question=question.slug):
                self.assertEqual(question.test_cases.count(), 10)
                self.assertEqual(question.test_cases.filter(is_sample=True, is_hidden=False).count(), 2)
                self.assertEqual(question.test_cases.filter(is_sample=False, is_hidden=True).count(), 8)
                self.assertIn("## Output Ordering", question.description)

            for language, code in (
                (Submission.Language.JAVA, question.java_reference_solution),
                (Submission.Language.PYTHON, question.python_reference_solution),
            ):
                with self.subTest(question=question.slug, language=language):
                    submission = Submission.objects.create(question=question, language=language, code=code)
                    run_submission(submission, question.test_cases.all())
                    submission.refresh_from_db()
                    self.assertEqual(submission.status, Submission.Status.ACCEPTED, submission.stderr or submission.stdout)
                    self.assertEqual(submission.passed_count, 10)
