from django.core.management.base import BaseCommand

from apps.core.models import Question, TestCase


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
                "starter_code": (
                    "def solve():\n"
                    "    numbers = list(map(int, input().split()))\n"
                    "    print(sum(numbers))\n\n\n"
                    "if __name__ == \"__main__\":\n"
                    "    solve()\n"
                ),
                "is_active": True,
            },
        )
        cases = [
            {"name": "Sample 1", "stdin": "1 2\n", "expected_output": "3\n", "is_sample": True, "is_hidden": False, "order": 1},
            {"name": "Hidden 1", "stdin": "10 25\n", "expected_output": "35\n", "is_sample": False, "is_hidden": True, "order": 2},
        ]
        created = 0
        for case in cases:
            _, was_created = TestCase.objects.get_or_create(question=question, name=case["name"], defaults=case)
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Sample problem ready. Created {created} test cases."))
