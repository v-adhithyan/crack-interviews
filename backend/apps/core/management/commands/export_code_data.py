import json

from django.core.management.base import BaseCommand

from apps.core.models import Question, Submission, TestCase, TestCaseResult


def serialize_datetime(value):
    return value.isoformat() if value else None


class Command(BaseCommand):
    help = "Export code questions, test cases, submissions, and results as portable JSON."

    def add_arguments(self, parser):
        parser.add_argument("--output", "-o", help="Path to write the JSON export. Defaults to stdout.")
        parser.add_argument(
            "--exclude-slug",
            action="append",
            default=["add-two-numbers"],
            help="Question slug to exclude. Can be passed more than once.",
        )

    def handle(self, *args, **options):
        excluded_slugs = set(options["exclude_slug"])
        questions = Question.objects.exclude(slug__in=excluded_slugs).order_by("title", "id")
        submissions = Submission.objects.filter(question__in=questions).select_related("question").order_by("created_at", "id")
        results = TestCaseResult.objects.filter(submission__in=submissions).select_related("test_case", "submission__question")

        results_by_submission_id = {}
        for result in results.order_by("submission_id", "test_case__order", "id"):
            results_by_submission_id.setdefault(result.submission_id, []).append(result)

        payload = {
            "version": 1,
            "excluded_slugs": sorted(excluded_slugs),
            "questions": [],
        }

        submissions_by_question_id = {}
        for submission in submissions:
            submissions_by_question_id.setdefault(submission.question_id, []).append(submission)

        for question in questions:
            question_payload = {
                "title": question.title,
                "slug": question.slug,
                "description": question.description,
                "difficulty": question.difficulty,
                "starter_code": question.starter_code,
                "java_starter_code": question.java_starter_code,
                "python_starter_code": question.python_starter_code,
                "execution_mode": question.execution_mode,
                "function_name": question.function_name,
                "is_active": question.is_active,
                "created_at": serialize_datetime(question.created_at),
                "updated_at": serialize_datetime(question.updated_at),
                "test_cases": [],
                "submissions": [],
            }

            for test_case in question.test_cases.order_by("order", "id"):
                question_payload["test_cases"].append(
                    {
                        "name": test_case.name,
                        "stdin": test_case.stdin,
                        "function_args": test_case.function_args,
                        "expected_value": test_case.expected_value,
                        "expected_output": test_case.expected_output,
                        "is_sample": test_case.is_sample,
                        "is_hidden": test_case.is_hidden,
                        "order": test_case.order,
                        "created_at": serialize_datetime(test_case.created_at),
                    }
                )

            for submission in submissions_by_question_id.get(question.id, []):
                submission_payload = {
                    "kind": submission.kind,
                    "language": submission.language,
                    "code": submission.code,
                    "status": submission.status,
                    "stdout": submission.stdout,
                    "stderr": submission.stderr,
                    "execution_time_ms": submission.execution_time_ms,
                    "solve_time_seconds": submission.solve_time_seconds,
                    "passed_count": submission.passed_count,
                    "total_count": submission.total_count,
                    "created_at": serialize_datetime(submission.created_at),
                    "results": [],
                }
                for result in results_by_submission_id.get(submission.id, []):
                    submission_payload["results"].append(
                        {
                            "test_case": {
                                "name": result.test_case.name,
                                "order": result.test_case.order,
                            },
                            "status": result.status,
                            "stdout": result.stdout,
                            "stderr": result.stderr,
                            "expected_output": result.expected_output,
                            "execution_time_ms": result.execution_time_ms,
                        }
                    )
                question_payload["submissions"].append(submission_payload)

            payload["questions"].append(question_payload)

        rendered = json.dumps(payload, indent=2, ensure_ascii=False)
        output_path = options["output"]
        if output_path:
            with open(output_path, "w", encoding="utf-8") as output_file:
                output_file.write(rendered)
                output_file.write("\n")
            self.stdout.write(self.style.SUCCESS(f"Exported {questions.count()} questions to {output_path}"))
            return

        self.stdout.write(rendered)
