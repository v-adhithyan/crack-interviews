from django.core.management import call_command
from django.db import migrations


def refresh_interview_questions(apps, schema_editor):
    call_command("seed_interview_track", create_missing=True, verbosity=0)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0019_question_comparison_mode"),
    ]

    operations = [
        migrations.RunPython(refresh_interview_questions, migrations.RunPython.noop),
    ]
