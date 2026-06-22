from django.core.management.base import BaseCommand

from apps.core.models import JAVA_STARTER_CODE, PYTHON_STARTER_CODE, Question, TestCase


class Command(BaseCommand):
    help = "Create a sample two-sum style problem for local smoke testing."

    def handle(self, *args, **options):
        question, _ = Question.objects.get_or_create(
            slug="add-two-numbers",
            defaults={
                "title": "Add Two Numbers",
                "difficulty": Question.Difficulty.EASY,
                "description": (
                    "Read two integers from standard input and print their sum.\n\n"
                    "Input:\nTwo integers separated by whitespace.\n\n"
                    "Output:\nThe sum of the two integers.\n\n"
                    "Example:\nInput: 1 2\nOutput: 3"
                ),
                "starter_code": JAVA_STARTER_CODE,
                "java_starter_code": JAVA_STARTER_CODE,
                "python_starter_code": PYTHON_STARTER_CODE,
                "is_active": True,
            },
        )
        updated_fields = []
        if question.java_starter_code != JAVA_STARTER_CODE:
            question.java_starter_code = JAVA_STARTER_CODE
            updated_fields.append("java_starter_code")
        if question.python_starter_code != PYTHON_STARTER_CODE:
            question.python_starter_code = PYTHON_STARTER_CODE
            updated_fields.append("python_starter_code")
        if question.starter_code != JAVA_STARTER_CODE:
            question.starter_code = JAVA_STARTER_CODE
            updated_fields.append("starter_code")
        if updated_fields:
            question.save(update_fields=updated_fields)
        cases = [
            {"name": "Sample 1", "stdin": "1 2\n", "expected_output": "3\n", "is_sample": True, "is_hidden": False, "order": 1},
            {"name": "Hidden 1", "stdin": "10 25\n", "expected_output": "35\n", "is_sample": False, "is_hidden": True, "order": 2},
        ]
        created = 0
        for case in cases:
            _, was_created = TestCase.objects.get_or_create(question=question, name=case["name"], defaults=case)
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Sample problem ready. Created {created} test cases."))
