import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0027_scratchpaddraft"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InterviewRoom",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("title", models.CharField(default="Problem solving interview", max_length=160)),
                ("problem_statement", models.TextField(blank=True)),
                ("language", models.CharField(choices=[("java", "Java 17"), ("python", "Python 3")], default="python", max_length=10)),
                ("code", models.TextField(blank=True)),
                ("stdin", models.TextField(blank=True)),
                ("candidate_name", models.CharField(blank=True, max_length=100)),
                ("candidate_joined_at", models.DateTimeField(blank=True, null=True)),
                ("is_closed", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("interviewer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="hosted_interview_rooms", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-updated_at",)},
        ),
    ]
