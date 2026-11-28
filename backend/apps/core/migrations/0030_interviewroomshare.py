from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0029_interviewroom_candidate_email"),
    ]

    operations = [
        migrations.CreateModel(
            name="InterviewRoomShare",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(max_length=254)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("room", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="hr_shares", to="core.interviewroom")),
            ],
            options={"ordering": ("email",)},
        ),
        migrations.AddConstraint(
            model_name="interviewroomshare",
            constraint=models.UniqueConstraint(fields=("room", "email"), name="unique_interview_room_hr_email"),
        ),
    ]
