from django.contrib import admin

from .models import BlogPost
from .models import EarlyAccessUser


@admin.register(EarlyAccessUser)
class EarlyAccessUserAdmin(admin.ModelAdmin):
    list_display = ("email", "is_beta_active", "created_at", "updated_at")
    list_filter = ("is_beta_active", "created_at", "updated_at")
    search_fields = ("email",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "author_name", "published_at", "updated_at")
    list_filter = ("status", "published_at", "created_at")
    search_fields = ("title", "excerpt", "content", "author_name")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "published_at"
    ordering = ("-published_at", "-created_at")
    fieldsets = (
        (None, {"fields": ("title", "slug", "excerpt", "content", "author_name", "status", "published_at")}),
        ("SEO", {"fields": ("seo_title", "seo_description")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
