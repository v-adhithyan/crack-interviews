from datetime import timedelta
from django.db import migrations
from django.utils import timezone

FUNCTION = 'apps.product.resume_pdf_jobs.cleanup_expired_pdfs'


def schedule_cleanup(apps, schema_editor):
    apps.get_model('django_q', 'Schedule').objects.using(schema_editor.connection.alias).get_or_create(
        func=FUNCTION,
        defaults={'name': 'Expire private resume PDFs', 'schedule_type': 'H',
                  'repeats': -1, 'next_run': timezone.now() + timedelta(hours=1)},
    )


def unschedule_cleanup(apps, schema_editor):
    apps.get_model('django_q', 'Schedule').objects.using(schema_editor.connection.alias).filter(func=FUNCTION).delete()


class Migration(migrations.Migration):
    dependencies = [('product', '0020_resumepdfjob'), ('django_q', '0017_task_cluster_alter')]
    operations = [migrations.RunPython(schedule_cleanup, unschedule_cleanup)]
