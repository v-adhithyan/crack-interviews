from django.db import models
from django.utils.text import slugify


class Question(models.Model):
    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField()
    difficulty = models.CharField(max_length=20, choices=Difficulty.choices, default=Difficulty.EASY)
    starter_code = models.TextField(default="def solve():\n    pass\n\n\nif __name__ == \"__main__\":\n    solve()\n")
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
    class Kind(models.TextChoices):
        RUN = "run", "Run"
        SUBMIT = "submit", "Submit"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        WRONG_ANSWER = "wrong_answer", "Wrong answer"
        RUNTIME_ERROR = "runtime_error", "Runtime error"
        TIME_LIMIT_EXCEEDED = "time_limit_exceeded", "Time limit exceeded"

    question = models.ForeignKey(Question, related_name="submissions", on_delete=models.CASCADE)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.SUBMIT)
    code = models.TextField()
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING)
    stdout = models.TextField(blank=True)
    stderr = models.TextField(blank=True)
    execution_time_ms = models.PositiveIntegerField(default=0)
    solve_time_seconds = models.PositiveIntegerField(null=True, blank=True)
    passed_count = models.PositiveIntegerField(default=0)
    total_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.question.title} - {self.get_status_display()}"


class TestCaseResult(models.Model):
    submission = models.ForeignKey(Submission, related_name="results", on_delete=models.CASCADE)
    test_case = models.ForeignKey(TestCase, on_delete=models.CASCADE)
    status = models.CharField(max_length=30, choices=Submission.Status.choices)
    stdout = models.TextField(blank=True)
    stderr = models.TextField(blank=True)
    expected_output = models.TextField(blank=True)
    execution_time_ms = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["test_case__order", "id"]

    def __str__(self):
        return f"{self.submission_id} - {self.test_case}"
