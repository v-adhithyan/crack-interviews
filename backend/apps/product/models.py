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
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        return self.original_filename
