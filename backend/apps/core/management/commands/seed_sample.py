from django.core.management.base import BaseCommand

from apps.core.models import JAVA_FUNCTION_STARTER_CODE, PYTHON_FUNCTION_STARTER_CODE, Question, TestCase


class Command(BaseCommand):
    help = "Create a sample two-sum style problem for local smoke testing."

    def handle(self, *args, **options):
        question, _ = Question.objects.get_or_create(
            slug="add-two-numbers",
            defaults={
                "title": "Add Two Numbers",
                "difficulty": Question.Difficulty.EASY,
                "description": (
                    "Implement a function that returns the sum of two integers.\n\n"
                    "Function signature:\nsolve(a, b)\n\n"
                    "Example:\nInput: a = 1, b = 2\nOutput: 3"
                ),
                "starter_code": JAVA_FUNCTION_STARTER_CODE,
                "java_starter_code": JAVA_FUNCTION_STARTER_CODE,
                "python_starter_code": PYTHON_FUNCTION_STARTER_CODE,
                "execution_mode": Question.ExecutionMode.FUNCTION,
                "function_name": "solve",
                "is_active": True,
            },
        )
        updated_fields = []
        if question.java_starter_code != JAVA_FUNCTION_STARTER_CODE:
            question.java_starter_code = JAVA_FUNCTION_STARTER_CODE
            updated_fields.append("java_starter_code")
        if question.python_starter_code != PYTHON_FUNCTION_STARTER_CODE:
            question.python_starter_code = PYTHON_FUNCTION_STARTER_CODE
            updated_fields.append("python_starter_code")
        if question.starter_code != JAVA_FUNCTION_STARTER_CODE:
            question.starter_code = JAVA_FUNCTION_STARTER_CODE
            updated_fields.append("starter_code")
        if question.execution_mode != Question.ExecutionMode.FUNCTION:
            question.execution_mode = Question.ExecutionMode.FUNCTION
            updated_fields.append("execution_mode")
        if question.function_name != "solve":
            question.function_name = "solve"
            updated_fields.append("function_name")
        if updated_fields:
            question.save(update_fields=updated_fields)
        cases = [
            {"name": "Sample 1", "function_args": [1, 2], "expected_value": 3, "expected_output": "3", "is_sample": True, "is_hidden": False, "order": 1},
            {"name": "Hidden 1", "function_args": [10, 25], "expected_value": 35, "expected_output": "35", "is_sample": False, "is_hidden": True, "order": 2},
        ]
        created = 0
        for case in cases:
            _, was_created = TestCase.objects.get_or_create(question=question, name=case["name"], defaults=case)
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Sample problem ready. Created {created} test cases."))
