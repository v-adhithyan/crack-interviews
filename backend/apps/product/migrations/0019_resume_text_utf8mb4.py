"""Repair legacy MySQL resume columns that cannot store four-byte Unicode."""
from django.db import migrations, models


def upgrade_resume_text(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "mysql":
        return

    for model_name in ("Resume", "ResumeAnalysis", "ResumeDraft"):
        model = apps.get_model("product", model_name)
        table = model._meta.db_table
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COLUMN_NAME, CHARACTER_SET_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
                [table],
            )
            charsets = dict(cursor.fetchall())
            cursor.execute(
                "SELECT TABLE_COLLATION FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
                [table],
            )
            table_collation = cursor.fetchone()[0]

        changes = []
        if not table_collation.startswith("utf8mb4_"):
            changes.append("DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        for field in model._meta.local_fields:
            # JSON has its own Unicode handling. Leave UUIDs, indexes and keys alone.
            if not isinstance(field, (models.CharField, models.TextField)):
                continue
            if charsets.get(field.column) == "utf8mb4":
                continue
            null_sql = "NULL" if field.null else "NOT NULL"
            changes.append(
                f"MODIFY COLUMN {schema_editor.quote_name(field.column)} "
                f"{field.db_type(connection)} CHARACTER SET utf8mb4 "
                f"COLLATE utf8mb4_unicode_ci {null_sql}"
            )
        if changes:
            schema_editor.execute(
                f"ALTER TABLE {schema_editor.quote_name(table)} " + ", ".join(changes)
            )


class Migration(migrations.Migration):
    atomic = False  # MySQL ALTER TABLE commits independently of transactions.
    dependencies = [("product", "0018_resume_builder_snapshot_and_more")]
    operations = [
        # Do not downgrade encodings on rollback: that could lose newly saved emoji.
        migrations.RunPython(upgrade_resume_text, migrations.RunPython.noop),
    ]
