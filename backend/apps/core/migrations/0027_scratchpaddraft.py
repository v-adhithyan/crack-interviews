from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0026_fix_equal_row_column_pairs"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ScratchpadDraft",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("java_code", models.TextField(blank=True)),
                ("python_code", models.TextField(blank=True)),
                ("selected_language", models.CharField(choices=[("java", "Java"), ("python", "Python")], default="python", max_length=10)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="scratchpad_draft", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
