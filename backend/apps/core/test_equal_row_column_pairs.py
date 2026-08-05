from django.core.management import call_command
from django.test import TestCase

from .executor import run_submission
from .models import Question, Submission


class EqualRowColumnPairsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_interview_track", create_missing=True, verbosity=0)
        cls.question = Question.objects.get(slug="equal-row-and-column-pairs")

    def test_all_expected_values_match_independent_brute_force(self):
        cases = self.question.test_cases.order_by("order")
        self.assertEqual(cases.count(), 10)
        self.assertEqual(cases.filter(is_sample=True).count(), 2)
        self.assertEqual(cases[1].function_args, [[[1, 2], [2, 1]]])
        self.assertEqual(cases[1].expected_value, 2)

        for case in cases:
            grid = case.function_args[0]
            expected = sum(row == [grid[index][column] for index in range(len(grid))] for row in grid for column in range(len(grid)))
            with self.subTest(case=case.name):
                self.assertEqual(case.expected_value, expected)

    def test_reference_solutions_pass_run_and_submit(self):
        for language, code in (
            (Submission.Language.JAVA, self.question.java_reference_solution),
            (Submission.Language.PYTHON, self.question.python_reference_solution),
        ):
            for kind, cases, expected_count in (
                (Submission.Kind.RUN, self.question.test_cases.filter(is_sample=True), 2),
                (Submission.Kind.SUBMIT, self.question.test_cases.all(), 10),
            ):
                with self.subTest(language=language, kind=kind):
                    submission = Submission.objects.create(question=self.question, language=language, code=code, kind=kind)
                    run_submission(submission, cases)
                    submission.refresh_from_db()
                    self.assertEqual(submission.status, Submission.Status.ACCEPTED, submission.stderr)
                    self.assertEqual(submission.passed_count, expected_count)
