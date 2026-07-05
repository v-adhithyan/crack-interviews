from django.db import migrations
from django.db import models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("product", "0012_userfeatureflags_can_access_coding_platform"),
    ]

    operations = [
        migrations.AddField(
            model_name="mockinterviewsession",
            name="continued_from",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="free_style_continuations",
                to="product.mockinterviewsession",
            ),
        ),
        migrations.AddField(
            model_name="mockinterviewsession",
            name="mode",
            field=models.CharField(
                choices=[("timed", "Timed"), ("free", "Free style")],
                default="timed",
                max_length=12,
            ),
        ),
    ]
