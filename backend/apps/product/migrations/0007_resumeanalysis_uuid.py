import uuid

from django.db import migrations, models


def populate_resume_analysis_uuids(apps, schema_editor):
    ResumeAnalysis = apps.get_model("product", "ResumeAnalysis")
    for analysis in ResumeAnalysis.objects.filter(uuid__isnull=True):
        analysis.uuid = uuid.uuid4()
        analysis.save(update_fields=("uuid",))


class Migration(migrations.Migration):

    dependencies = [
        ("product", "0006_resumeanalysis_background_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="resumeanalysis",
            name="uuid",
            field=models.UUIDField(blank=True, null=True, editable=False),
        ),
        migrations.RunPython(populate_resume_analysis_uuids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="resumeanalysis",
            name="uuid",
            field=models.UUIDField(default=uuid.uuid4, unique=True, editable=False),
        ),
    ]
