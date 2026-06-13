import uuid

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.urls import path
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import BlogPost
from .models import EarlyAccessUser
from .models import PricingSuggestion
from .models import WebsitePage


@admin.register(EarlyAccessUser)
class EarlyAccessUserAdmin(admin.ModelAdmin):
    actions = ("activate_beta_and_refresh_signup_links",)
    list_display = ("email", "is_beta_active", "signup_link", "signup_completed_at", "user", "created_at", "updated_at")
    list_filter = ("is_beta_active", "signup_completed_at", "created_at", "updated_at")
    search_fields = ("email", "user__email", "user__username")
    ordering = ("-created_at",)
    readonly_fields = ("signup_link", "signup_token", "signup_token_created_at", "signup_completed_at", "user", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("email", "is_beta_active", "signup_link")}),
        ("Signup", {"fields": ("signup_token", "signup_token_created_at", "signup_completed_at", "date_of_birth", "user")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def signup_link(self, obj):
        if not obj.pk:
            return "Save this early access user before copying a signup link."

        url = reverse("early_access_signup", kwargs={"token": obj.signup_token})
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', url, url)

    signup_link.short_description = "Signup link"

    @admin.action(description="Activate beta access and refresh signup links")
    def activate_beta_and_refresh_signup_links(self, request, queryset):
        updated = 0
        for early_access_user in queryset:
            if early_access_user.has_completed_signup:
                continue
            early_access_user.is_beta_active = True
            early_access_user.signup_token = uuid.uuid4()
            early_access_user.signup_token_created_at = timezone.now()
            early_access_user.save(update_fields=("is_beta_active", "signup_token", "signup_token_created_at", "updated_at"))
            updated += 1
        self.message_user(request, f"{updated} signup link(s) refreshed and marked beta active.")


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "author_name", "published_at", "updated_at")
    list_filter = ("status", "published_at", "created_at")
    search_fields = ("title", "excerpt", "content", "author_name")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("preview_link", "created_at", "updated_at")
    date_hierarchy = "published_at"
    ordering = ("-published_at", "-created_at")
    fieldsets = (
        (None, {"fields": ("title", "slug", "excerpt", "content", "author_name", "status", "published_at", "preview_link")}),
        ("SEO", {"fields": ("seo_title", "seo_description")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/preview/",
                self.admin_site.admin_view(self.preview_view),
                name="website_blogpost_preview",
            ),
        ]
        return custom_urls + urls

    def preview_link(self, obj):
        if not obj.pk:
            return "Save this blog post before previewing it."

        url = reverse("admin:website_blogpost_preview", args=[obj.pk])
        return format_html('<a class="button" href="{}" target="_blank" rel="noopener">Preview blog post</a>', url)

    preview_link.short_description = "Preview"

    def preview_view(self, request, object_id):
        if not request.user.is_superuser:
            raise PermissionDenied

        post = get_object_or_404(BlogPost, pk=object_id)
        return render(request, "website/blog/detail.html", {"post": post})


@admin.register(PricingSuggestion)
class PricingSuggestionAdmin(admin.ModelAdmin):
    list_display = ("price", "no_of_months", "ip_address", "session_key", "created_at")
    list_filter = ("price", "no_of_months", "created_at")
    search_fields = ("session_key", "ip_address")
    readonly_fields = ("created_at", "updated_at", "metadata")
    ordering = ("-created_at",)


@admin.register(WebsitePage)
class WebsitePageAdmin(admin.ModelAdmin):
    list_display = ("title", "page_type", "slug", "is_published", "updated_at")
    list_filter = ("page_type", "is_published", "created_at")
    search_fields = ("title", "excerpt", "content")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at")
    ordering = ("page_type", "title")
    fieldsets = (
        (None, {"fields": ("title", "slug", "page_type", "excerpt", "content", "is_published")}),
        ("SEO", {"fields": ("seo_title", "seo_description")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
