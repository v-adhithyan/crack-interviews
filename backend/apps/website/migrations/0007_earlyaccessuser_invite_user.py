import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def populate_signup_tokens(apps, schema_editor):
    early_access_user = apps.get_model("website", "EarlyAccessUser")
    for user in early_access_user.objects.filter(signup_token__isnull=True):
        user.signup_token = uuid.uuid4()
        user.save(update_fields=("signup_token",))


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("website", "0006_websitepage"),
    ]

    operations = [
        migrations.AddField(
            model_name="earlyaccessuser",
            name="signup_token",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="earlyaccessuser",
            name="signup_token_created_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name="earlyaccessuser",
            name="signup_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="earlyaccessuser",
            name="date_of_birth",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="earlyaccessuser",
            name="user",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="early_access_invite",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(populate_signup_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="earlyaccessuser",
            name="signup_token",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
