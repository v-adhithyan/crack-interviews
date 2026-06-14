import uuid

from django.db import migrations, models


def populate_resume_uuids(apps, schema_editor):
    resume_model = apps.get_model("product", "Resume")
    for resume in resume_model.objects.filter(uuid__isnull=True):
        resume.uuid = uuid.uuid4()
        resume.save(update_fields=("uuid",))


class Migration(migrations.Migration):

    dependencies = [
        ("product", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="resume",
            name="uuid",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(populate_resume_uuids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="resume",
            name="uuid",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
