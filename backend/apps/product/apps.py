from django.apps import AppConfig


class ProductConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.product"
    label = "product"

    def ready(self):
        from . import resume_pdf_jobs  # Register artifact cleanup on deletion.
