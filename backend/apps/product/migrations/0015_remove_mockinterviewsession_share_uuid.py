from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("product", "0014_mockinterviewsession_share_uuid"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="mockinterviewsession",
            name="share_uuid",
        ),
    ]
