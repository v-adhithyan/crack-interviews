from django.contrib import admin

from .models import EarlyAccessUser


@admin.register(EarlyAccessUser)
class EarlyAccessUserAdmin(admin.ModelAdmin):
    list_display = ("email", "is_beta_active", "created_at", "updated_at")
    list_filter = ("is_beta_active", "created_at", "updated_at")
    search_fields = ("email",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")
