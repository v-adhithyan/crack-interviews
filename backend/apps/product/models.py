import uuid

from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils import timezone


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
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        PROMPT_READY = "prompt_ready", "Prompt Ready"
        RESULT_ADDED = "result_added", "Result Added"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resume_analyses")
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name="analyses")
    job_description = models.TextField()
    resume_text = models.TextField()
    generated_prompt = models.TextField()
    ai_response_json = models.JSONField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROMPT_READY)
    task_id = models.CharField(max_length=255, blank=True)
    ai_provider = models.CharField(max_length=40, blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
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
        return {
            self.Status.QUEUED: "Queued",
            self.Status.PROCESSING: "Processing",
            self.Status.PROMPT_READY: "Prompt Ready",
            self.Status.RESULT_ADDED: "Completed",
            self.Status.FAILED: "Failed",
        }.get(self.status, "Prompt Ready")

    @property
    def is_queued_or_processing(self):
        return self.status in {self.Status.QUEUED, self.Status.PROCESSING}

    @property
    def is_failed(self):
        return self.status == self.Status.FAILED

    @property
    def progress_percent(self):
        if self.status == self.Status.RESULT_ADDED:
            return 100
        if self.status == self.Status.FAILED:
            return 100
        if self.status == self.Status.QUEUED:
            return 15
        if self.status == self.Status.PROCESSING:
            if not self.started_at:
                return 40
            elapsed_seconds = max(0, (timezone.now() - self.started_at).total_seconds())
            return min(90, 40 + int(elapsed_seconds // 3) * 5)
        return 0

    @property
    def progress_label(self):
        if self.status == self.Status.QUEUED:
            return "Queued for analysis"
        if self.status == self.Status.PROCESSING:
            return "Analyzing resume"
        if self.status == self.Status.RESULT_ADDED:
            return "Analysis complete"
        if self.status == self.Status.FAILED:
            return "Analysis failed"
        return self.display_status


class UserFeatureFlags(models.Model):
    DEFAULT_AI_ANALYSIS_DAILY_LIMIT = 2
    DEFAULT_MOCK_INTERVIEW_DAILY_LIMIT = 1

    class AIMode(models.TextChoices):
        MANUAL = "manual", "Manual"
        CHATGPT = "chatgpt", "ChatGPT"
        CLAUDE = "claude", "Claude"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="feature_flags")
    ai_mode = models.CharField(max_length=20, choices=AIMode.choices, blank=True, null=True)
    ai_analysis_daily_limit = models.PositiveSmallIntegerField(default=DEFAULT_AI_ANALYSIS_DAILY_LIMIT)
    ai_analysis_window_started_at = models.DateTimeField(blank=True, null=True)
    ai_analysis_count = models.PositiveSmallIntegerField(default=0)
    mock_interview_daily_limit = models.PositiveSmallIntegerField(default=DEFAULT_MOCK_INTERVIEW_DAILY_LIMIT)
    mock_interview_window_started_at = models.DateTimeField(blank=True, null=True)
    mock_interview_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "product_user_feature_flags"
        verbose_name = "User Feature Flags"
        verbose_name_plural = "User Feature Flags"

    def __str__(self):
        mode = self.ai_mode or "default"
        return f"{self.user} feature flags: resume analysis mode {mode}"

    def reset_ai_analysis_usage_if_expired(self, now=None):
        now = now or timezone.now()
        if self.ai_analysis_window_started_at and now - self.ai_analysis_window_started_at >= timedelta(hours=24):
            self.ai_analysis_window_started_at = None
            self.ai_analysis_count = 0
            self.save(update_fields=("ai_analysis_window_started_at", "ai_analysis_count", "updated_at"))

    @property
    def ai_analysis_quota_remaining(self):
        return max(0, self.ai_analysis_daily_limit - self.ai_analysis_count)

    def can_run_ai_analysis(self, now=None):
        self.reset_ai_analysis_usage_if_expired(now=now)
        return self.ai_analysis_daily_limit > 0 and self.ai_analysis_count < self.ai_analysis_daily_limit

    def consume_ai_analysis_quota(self, now=None):
        now = now or timezone.now()
        self.reset_ai_analysis_usage_if_expired(now=now)
        if not self.can_run_ai_analysis(now=now):
            return False
        if not self.ai_analysis_window_started_at:
            self.ai_analysis_window_started_at = now
        self.ai_analysis_count += 1
        self.save(update_fields=("ai_analysis_window_started_at", "ai_analysis_count", "updated_at"))
        return True

    def reset_mock_interview_usage_if_expired(self, now=None):
        now = now or timezone.now()
        if self.mock_interview_window_started_at and now - self.mock_interview_window_started_at >= timedelta(hours=24):
            self.mock_interview_window_started_at = None
            self.mock_interview_count = 0
            self.save(update_fields=("mock_interview_window_started_at", "mock_interview_count", "updated_at"))

    @property
    def mock_interview_quota_remaining(self):
        return max(0, self.mock_interview_daily_limit - self.mock_interview_count)

    def can_run_mock_interview(self, now=None):
        self.reset_mock_interview_usage_if_expired(now=now)
        return self.mock_interview_daily_limit > 0 and self.mock_interview_count < self.mock_interview_daily_limit

    def consume_mock_interview_quota(self, now=None):
        now = now or timezone.now()
        self.reset_mock_interview_usage_if_expired(now=now)
        if not self.can_run_mock_interview(now=now):
            return False
        if not self.mock_interview_window_started_at:
            self.mock_interview_window_started_at = now
        self.mock_interview_count += 1
        self.save(update_fields=("mock_interview_window_started_at", "mock_interview_count", "updated_at"))
        return True


ResumeAnalysisSettings = UserFeatureFlags


class MockInterviewSession(models.Model):
    class TopicSource(models.TextChoices):
        PRESET = "preset", "Preset"
        CUSTOM = "custom", "Custom"

    class Level(models.TextChoices):
        MID = "mid", "Mid-level"
        SENIOR = "senior", "Senior"
        STAFF = "staff", "Staff"

    class Status(models.TextChoices):
        CREATED = "created", "Created"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mock_interview_sessions")
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    topic_source = models.CharField(max_length=12, choices=TopicSource.choices, default=TopicSource.PRESET)
    topic = models.CharField(max_length=1000)
    level = models.CharField(max_length=12, choices=Level.choices, default=Level.SENIOR)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CREATED)
    transcript_text = models.TextField(blank=True)
    feedback_json = models.JSONField(blank=True, null=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(blank=True, null=True)
    ended_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        db_table = "product_mock_interview_session"

    def __str__(self):
        return f"{self.get_level_display()} mock interview: {self.topic[:80]}"

    @property
    def display_score(self):
        if not self.feedback_json:
            return None
        score = self.feedback_json.get("overall_score")
        try:
            return int(score)
        except (TypeError, ValueError):
            return None


class MockInterviewTurn(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        INTERVIEWER = "interviewer", "Interviewer"

    session = models.ForeignKey(MockInterviewSession, on_delete=models.CASCADE, related_name="turns")
    role = models.CharField(max_length=20, choices=Role.choices)
    text = models.TextField()
    occurred_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("occurred_at", "id")
        db_table = "product_mock_interview_turn"

    def __str__(self):
        return f"{self.get_role_display()}: {self.text[:80]}"
