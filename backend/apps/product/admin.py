from django.contrib import admin

from .models import Resume
from .models import ResumeAnalysis


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "user", "uuid", "content_type", "size", "updated_at")
    list_filter = ("content_type", "uploaded_at", "updated_at")
    search_fields = ("original_filename", "uuid", "user__username", "user__email", "parsed_text")
    readonly_fields = ("uuid", "user", "file", "original_filename", "content_type", "size", "parsed_text", "uploaded_at", "updated_at")


@admin.register(ResumeAnalysis)
class ResumeAnalysisAdmin(admin.ModelAdmin):
    list_display = ("resume", "user", "status", "updated_at")
    list_filter = ("status", "created_at", "updated_at")
    search_fields = ("resume__original_filename", "user__username", "user__email", "job_description", "resume_text")
    readonly_fields = ("created_at", "updated_at")
