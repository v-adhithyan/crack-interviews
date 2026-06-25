import secrets

from django.conf import settings
from django.db import models
from django.utils.text import slugify


JAVA_STARTER_CODE = (
    "import java.io.*;\n"
    "import java.util.*;\n\n"
    "public class Main {\n"
    "    public static void main(String[] args) throws Exception {\n"
    "        Scanner scanner = new Scanner(System.in);\n"
    "        int sum = 0;\n"
    "        while (scanner.hasNextInt()) {\n"
    "            sum += scanner.nextInt();\n"
    "        }\n"
    "        System.out.println(sum);\n"
    "    }\n"
    "}\n"
)

PYTHON_STARTER_CODE = (
    "def solve():\n"
    "    numbers = list(map(int, input().split()))\n"
    "    print(sum(numbers))\n\n\n"
    "if __name__ == \"__main__\":\n"
    "    solve()\n"
)

JAVA_FUNCTION_STARTER_CODE = (
    "import java.util.*;\n\n"
    "class Solution {\n"
    "    public int solve(int a, int b) {\n"
    "        return a + b;\n"
    "    }\n"
    "}\n"
)

PYTHON_FUNCTION_STARTER_CODE = (
    "def solve(a, b):\n"
    "    return a + b\n"
)


class Question(models.Model):
    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    class ExecutionMode(models.TextChoices):
        STDIN = "stdin", "Standard input"
        FUNCTION = "function", "Function call"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField()
    difficulty = models.CharField(max_length=20, choices=Difficulty.choices, default=Difficulty.EASY)
    starter_code = models.TextField(default=JAVA_STARTER_CODE)
    java_starter_code = models.TextField(default=JAVA_STARTER_CODE)
    python_starter_code = models.TextField(default=PYTHON_STARTER_CODE)
    java_reference_solution = models.TextField(blank=True)
    python_reference_solution = models.TextField(blank=True)
    execution_mode = models.CharField(max_length=20, choices=ExecutionMode.choices, default=ExecutionMode.STDIN)
    function_name = models.CharField(max_length=80, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class TestCase(models.Model):
    question = models.ForeignKey(Question, related_name="test_cases", on_delete=models.CASCADE)
    name = models.CharField(max_length=200, blank=True)
    stdin = models.TextField(blank=True)
    function_args = models.JSONField(blank=True, null=True)
    expected_value = models.JSONField(blank=True, null=True)
    expected_output = models.TextField()
    is_sample = models.BooleanField(default=False)
    is_hidden = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name or f"{self.question.title} case #{self.pk}"


class Submission(models.Model):
    class Language(models.TextChoices):
        JAVA = "java", "Java 17"
        PYTHON = "python", "Python 3"

    class Kind(models.TextChoices):
        RUN = "run", "Run"
        SUBMIT = "submit", "Submit"
        CUSTOM = "custom", "Custom"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        WRONG_ANSWER = "wrong_answer", "Wrong answer"
        RUNTIME_ERROR = "runtime_error", "Runtime error"
        TIME_LIMIT_EXCEEDED = "time_limit_exceeded", "Time limit exceeded"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="code_submissions", on_delete=models.CASCADE, null=True, blank=True)
    question = models.ForeignKey(Question, related_name="submissions", on_delete=models.CASCADE)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.SUBMIT)
    language = models.CharField(max_length=20, choices=Language.choices, default=Language.JAVA)
    code = models.TextField()
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING)
    stdout = models.TextField(blank=True)
    stderr = models.TextField(blank=True)
    execution_time_ms = models.PositiveIntegerField(default=0)
    memory_kb = models.PositiveIntegerField(default=0)
    solve_time_seconds = models.PositiveIntegerField(null=True, blank=True)
    marked_for_revision = models.BooleanField(default=False)
    passed_count = models.PositiveIntegerField(default=0)
    total_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.question.title} - {self.get_status_display()}"


class AdminApiToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="admin_api_tokens", on_delete=models.CASCADE)
    token = models.CharField(max_length=96, unique=True, default=secrets.token_urlsafe)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"API token for {self.user}"


class TestCaseResult(models.Model):
    submission = models.ForeignKey(Submission, related_name="results", on_delete=models.CASCADE)
    test_case = models.ForeignKey(TestCase, on_delete=models.CASCADE, blank=True, null=True)
    custom_name = models.CharField(max_length=200, blank=True)
    custom_input = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=Submission.Status.choices)
    stdout = models.TextField(blank=True)
    stderr = models.TextField(blank=True)
    expected_output = models.TextField(blank=True)
    execution_time_ms = models.PositiveIntegerField(default=0)
    memory_kb = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["test_case__order", "id"]

    def __str__(self):
        return f"{self.submission_id} - {self.test_case}"
