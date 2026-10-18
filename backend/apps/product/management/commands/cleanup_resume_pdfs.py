from django.core.management.base import BaseCommand
from apps.product.resume_pdf_jobs import cleanup_expired_pdfs


class Command(BaseCommand):
    help = 'Delete expired private PDF jobs and their files (also scheduled hourly).'

    def handle(self, *args, **options):
        count = cleanup_expired_pdfs()
        self.stdout.write(f'Deleted {count} expired PDF jobs.')
