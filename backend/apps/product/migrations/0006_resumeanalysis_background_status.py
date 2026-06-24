from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("product", "0005_quickrefreshsettings_quickrefreshnote"),
    ]

    operations = [
        migrations.AlterField(
            model_name="resumeanalysis",
            name="status",
            field=models.CharField(
                choices=[
                    ("queued", "Queued"),
                    ("processing", "Processing"),
                    ("prompt_ready", "Prompt Ready"),
                    ("result_added", "Result Added"),
                    ("failed", "Failed"),
                ],
                default="prompt_ready",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="resumeanalysis",
            name="task_id",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="resumeanalysis",
            name="ai_provider",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="resumeanalysis",
            name="error_message",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="resumeanalysis",
            name="started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="resumeanalysis",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
