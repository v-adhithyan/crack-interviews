from django.db import models
from django.utils import timezone


class EarlyAccessUser(models.Model):
    email = models.EmailField(unique=True, blank=False, null=False)
    is_beta_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.email


class BlogPost(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    title = models.CharField(max_length=220)
    slug = models.SlugField(max_length=240, unique=True)
    excerpt = models.TextField(max_length=420)
    content = models.TextField()
    author_name = models.CharField(max_length=120, default="Adhi")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(blank=True, null=True)
    seo_title = models.CharField(max_length=220, blank=True)
    seo_description = models.CharField(max_length=320, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-published_at", "-created_at")

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.status == self.Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def is_published(self):
        return self.status == self.Status.PUBLISHED and self.published_at is not None

    @property
    def meta_title(self):
        return self.seo_title or self.title

    @property
    def meta_description(self):
        return self.seo_description or self.excerpt


class PricingSuggestion(models.Model):
    price = models.PositiveIntegerField(blank=False, null=False, default=100)
    no_of_months = models.PositiveIntegerField(blank=False, null=False, default=1)
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f'{self.price} - {self.no_of_months}'


class WebsitePage(models.Model):
    class PageType(models.TextChoices):
        ABOUT = "about", "About"
        FAQ = "faq", "FAQ"

    title = models.CharField(max_length=220)
    slug = models.SlugField(max_length=240, unique=True)
    page_type = models.CharField(max_length=20, choices=PageType.choices)
    excerpt = models.TextField(max_length=420)
    content = models.TextField(help_text="HTML is supported for trusted CMS content.")
    is_published = models.BooleanField(default=True)
    seo_title = models.CharField(max_length=220, blank=True)
    seo_description = models.CharField(max_length=320, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("page_type", "title")

    def __str__(self):
        return self.title

    @property
    def meta_title(self):
        return self.seo_title or self.title

    @property
    def meta_description(self):
        return self.seo_description or self.excerpt
