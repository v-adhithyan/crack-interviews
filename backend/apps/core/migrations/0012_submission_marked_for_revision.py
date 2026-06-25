from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0011_submission_memory_kb_testcaseresult_memory_kb"),
    ]

    operations = [
        migrations.AddField(
            model_name="submission",
            name="marked_for_revision",
            field=models.BooleanField(default=False),
        ),
    ]
