from django.core.management import call_command
from django.db import migrations


def refresh_interview_examples(apps, schema_editor):
    call_command("seed_interview_track", create_missing=True, verbosity=0)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0024_refine_interview_question_descriptions"),
    ]

    operations = [
        migrations.RunPython(refresh_interview_examples, migrations.RunPython.noop),
    ]
