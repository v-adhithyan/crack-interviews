from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0018_refresh_interview_node_questions"),
    ]

    operations = [
        migrations.AddField(
            model_name="question",
            name="comparison_mode",
            field=models.CharField(
                choices=[
                    ("ordered", "Order matters"),
                    ("unordered_list", "List order does not matter"),
                    ("unordered_nested_lists", "Outer and inner list order does not matter"),
                ],
                default="ordered",
                max_length=32,
            ),
        ),
    ]
