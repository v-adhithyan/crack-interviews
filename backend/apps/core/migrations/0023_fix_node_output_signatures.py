from django.core.management import call_command
from django.db import migrations


def refresh_node_output_signatures(apps, schema_editor):
    call_command("seed_interview_track", create_missing=True, verbosity=0)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0022_fix_node_parameter_signatures"),
    ]

    operations = [
        migrations.RunPython(refresh_node_output_signatures, migrations.RunPython.noop),
    ]
