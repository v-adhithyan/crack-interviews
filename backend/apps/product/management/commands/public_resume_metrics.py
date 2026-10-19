from django.core.management.base import BaseCommand
from apps.product.models import PublicBuilderCounter, PublicResumePdfJob


class Command(BaseCommand):
    help = 'Report aggregate public resume funnel events and current PDF queue state.'

    def handle(self, *args, **options):
        for key, count in PublicBuilderCounter.objects.filter(key__startswith='metric:').order_by('key').values_list('key', 'count'):
            self.stdout.write(f'{key} {count}')
        for state in ['queued', 'processing', 'ready', 'failed']:
            self.stdout.write(f'pdf_current_{state} {PublicResumePdfJob.objects.filter(status=state).count()}')
