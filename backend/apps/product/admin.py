from django.contrib import admin

from apps.core.admin_permissions import ReadOnlyModelAdmin

from .models import (
    AIIntegration,
    AnalysisFollowup,
    InterviewSimulatorSession,
    MockInterviewSession,
    MockInterviewTurn,
    PublicBuilderCounter,
    PublicBuilderGate,
    PublicResumePdfJob,
    PublicResumeTransfer,
    Resume,
    ResumeAnalysis,
    ResumeDraft,
    ResumeEditApplication,
    ResumePdfJob,
    ResumePrunePlan,
    UserFeatureFlags,
)


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "user", "uuid", "content_type", "size", "updated_at")
    list_filter = ("content_type", "uploaded_at", "updated_at")
    search_fields = ("original_filename", "uuid", "user__username", "user__email", "parsed_text")
    readonly_fields = ("uuid", "user", "file", "original_filename", "content_type", "size", "parsed_text", "uploaded_at", "updated_at")


@admin.register(ResumeAnalysis)
class ResumeAnalysisAdmin(admin.ModelAdmin):
    list_display = ("resume", "user", "status", "ai_provider", "task_id", "updated_at")
    list_filter = ("status", "ai_provider", "created_at", "updated_at")
    search_fields = ("resume__original_filename", "user__username", "user__email", "job_description", "resume_text", "task_id")
    readonly_fields = ("task_id", "started_at", "completed_at", "created_at", "updated_at")


@admin.register(UserFeatureFlags)
class UserFeatureFlagsAdmin(admin.ModelAdmin):
    list_display = ("user", "can_access_coding_platform", "ai_mode", "ai_analysis_daily_limit", "ai_analysis_count", "mock_interview_daily_limit", "mock_interview_count", "updated_at")
    list_filter = ("can_access_coding_platform", "ai_mode", "created_at", "updated_at")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("created_at", "updated_at")


class MockInterviewTurnInline(admin.TabularInline):
    model = MockInterviewTurn
    extra = 0
    readonly_fields = ("role", "text", "occurred_at", "created_at")
    can_delete = False


@admin.register(MockInterviewSession)
class MockInterviewSessionAdmin(admin.ModelAdmin):
    list_display = ("topic", "user", "mode", "topic_source", "level", "status", "started_at", "ended_at", "updated_at")
    list_filter = ("mode", "topic_source", "level", "status", "created_at", "updated_at")
    search_fields = ("topic", "user__username", "user__email", "transcript_text", "error_message")
    readonly_fields = ("uuid", "continued_from", "transcript_text", "feedback_json", "error_message", "started_at", "ended_at", "created_at", "updated_at")
    inlines = (MockInterviewTurnInline,)


@admin.register(MockInterviewTurn)
class MockInterviewTurnAdmin(admin.ModelAdmin):
    list_display = ("session", "role", "occurred_at", "created_at")
    list_filter = ("role", "occurred_at", "created_at")
    search_fields = ("text", "session__topic", "session__user__username", "session__user__email")
    readonly_fields = ("session", "role", "text", "occurred_at", "created_at")


admin.site.register(
    [
        AnalysisFollowup,
        InterviewSimulatorSession,
        PublicBuilderCounter,
        PublicBuilderGate,
        PublicResumePdfJob,
        PublicResumeTransfer,
        ResumeDraft,
        ResumeEditApplication,
        ResumePdfJob,
        ResumePrunePlan,
    ],
    ReadOnlyModelAdmin,
)


@admin.register(AIIntegration)
class AIIntegrationAdmin(ReadOnlyModelAdmin):
    fields = ("user",)
    list_display = ("user",)

    def lookup_allowed(self, lookup, value, request=None):
        if lookup.split("__", 1)[0] == "encrypted_api_key":
            return False
        return super().lookup_allowed(lookup, value, request)
