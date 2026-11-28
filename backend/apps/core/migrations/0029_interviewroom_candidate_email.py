from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0028_interviewroom"),
    ]

    operations = [
        migrations.AddField(
            model_name="interviewroom",
            name="candidate_email",
            field=models.EmailField(blank=True, max_length=254),
        ),
    ]
