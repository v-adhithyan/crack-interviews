from django.db import migrations


def drop_stale_share_uuid_column(apps, schema_editor):
    MockInterviewSession = apps.get_model("product", "MockInterviewSession")
    table_name = MockInterviewSession._meta.db_table
    connection = schema_editor.connection

    with connection.cursor() as cursor:
        columns = {
            column.name
            for column in connection.introspection.get_table_description(cursor, table_name)
        }

    if "share_uuid" not in columns:
        return

    quoted_table = schema_editor.quote_name(table_name)
    quoted_column = schema_editor.quote_name("share_uuid")
    schema_editor.execute(f"ALTER TABLE {quoted_table} DROP COLUMN {quoted_column}")


class Migration(migrations.Migration):
    dependencies = [
        ("product", "0015_remove_mockinterviewsession_share_uuid"),
    ]

    operations = [
        migrations.RunPython(drop_stale_share_uuid_column, migrations.RunPython.noop),
    ]
