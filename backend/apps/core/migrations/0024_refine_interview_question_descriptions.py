from django.core.management import call_command
from django.db import migrations


def refresh_interview_question_descriptions(apps, schema_editor):
    call_command("seed_interview_track", create_missing=True, verbosity=0)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0023_fix_node_output_signatures"),
    ]

    operations = [
        migrations.RunPython(refresh_interview_question_descriptions, migrations.RunPython.noop),
    ]
