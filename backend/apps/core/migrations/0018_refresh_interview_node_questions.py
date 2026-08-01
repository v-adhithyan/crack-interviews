from django.core.management import call_command
from django.db import migrations


def refresh_interview_node_questions(apps, schema_editor):
    call_command("seed_interview_track", create_missing=True, verbosity=0)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0017_interview_track_manual_rollback"),
    ]

    operations = [
        migrations.RunPython(refresh_interview_node_questions, migrations.RunPython.noop),
    ]
