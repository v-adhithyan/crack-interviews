from django.contrib import admin

from .models import Resume


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "user", "uuid", "content_type", "size", "updated_at")
    list_filter = ("content_type", "uploaded_at", "updated_at")
    search_fields = ("original_filename", "uuid", "user__username", "user__email")
    readonly_fields = ("uuid", "user", "file", "original_filename", "content_type", "size", "uploaded_at", "updated_at")
