from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_question_java_reference_solution_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="submission",
            name="memory_kb",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="testcaseresult",
            name="memory_kb",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
