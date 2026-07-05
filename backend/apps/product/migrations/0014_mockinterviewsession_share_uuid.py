import uuid

from django.db import migrations
from django.db import models


def backfill_share_uuids(apps, schema_editor):
    MockInterviewSession = apps.get_model("product", "MockInterviewSession")
    for session in MockInterviewSession.objects.filter(share_uuid__isnull=True):
        session.share_uuid = uuid.uuid4()
        session.save(update_fields=("share_uuid",))


class Migration(migrations.Migration):

    dependencies = [
        ("product", "0013_mockinterviewsession_continuation_mode"),
    ]

    operations = [
        migrations.AddField(
            model_name="mockinterviewsession",
            name="share_uuid",
            field=models.UUIDField(default=uuid.uuid4, editable=False, null=True),
        ),
        migrations.RunPython(backfill_share_uuids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="mockinterviewsession",
            name="share_uuid",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
