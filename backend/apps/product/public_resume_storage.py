from django.conf import settings
from django.core.files.storage import FileSystemStorage


def public_pdf_storage():
    # Intentionally outside MEDIA_ROOT: never expose via the media/static server.
    return FileSystemStorage(location=settings.PUBLIC_RESUME_PDF_ROOT, base_url=None)
