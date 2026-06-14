import uuid

from pathlib import Path

from django.conf import settings
from django.db import models


def resume_upload_path(instance, filename):
    extension = Path(filename).suffix.lower()
    return f"private/resumes/user_{instance.user_id}/resume{extension}"


class Resume(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resume")
    file = models.FileField(upload_to=resume_upload_path)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120)
    size = models.PositiveIntegerField()
    parsed_text = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        return self.original_filename


class ResumeAnalysis(models.Model):
    class Status(models.TextChoices):
        PROMPT_READY = "prompt_ready", "Prompt Ready"
        RESULT_ADDED = "result_added", "Result Added"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resume_analyses")
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name="analyses")
    job_description = models.TextField()
    resume_text = models.TextField()
    generated_prompt = models.TextField()
    ai_response_json = models.JSONField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROMPT_READY)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        return f"Analysis for {self.resume.original_filename}"

    @property
    def result_data(self):
        return self.ai_response_json or {}

    @property
    def display_title(self):
        return self.result_data.get("role_title_detected") or "Resume Match Analysis"

    @property
    def display_company(self):
        return self.result_data.get("company_detected") or "Not detected"

    @property
    def display_score(self):
        score = self.result_data.get("overall_match_score")
        if score is None:
            return None
        try:
            return int(score)
        except (TypeError, ValueError):
            return None

    @property
    def has_score(self):
        return self.display_score is not None

    @property
    def score_tone(self):
        score = self.display_score
        if score is None:
            return "neutral"
        if score >= 80:
            return "good"
        if score >= 60:
            return "warn"
        return "low"

    @property
    def display_status(self):
        if self.status == self.Status.RESULT_ADDED:
            return "Completed"
        return "Prompt Ready"
