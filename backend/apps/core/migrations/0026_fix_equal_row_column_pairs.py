from django.core.management import call_command
from django.db import migrations


def refresh_equal_row_column_pairs(apps, schema_editor):
    call_command("seed_interview_track", create_missing=True, verbosity=0)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0025_refine_interview_examples"),
    ]

    operations = [
        migrations.RunPython(refresh_equal_row_column_pairs, migrations.RunPython.noop),
    ]
