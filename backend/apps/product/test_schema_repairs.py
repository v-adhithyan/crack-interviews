import importlib

from django.apps import apps
from django.db import connection
from django.test import TransactionTestCase

from .models import MockInterviewSession


class MockInterviewSchemaRepairTests(TransactionTestCase):
    def test_stale_share_uuid_column_is_removed_idempotently(self):
        migration = importlib.import_module("apps.product.migrations.0016_repair_stale_share_uuid_column")
        table_name = MockInterviewSession._meta.db_table
        quoted_table = connection.ops.quote_name(table_name)
        quoted_column = connection.ops.quote_name("share_uuid")

        with connection.cursor() as cursor:
            cursor.execute(f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_column} varchar(36) NOT NULL DEFAULT 'stale'")

        with connection.schema_editor() as schema_editor:
            migration.drop_stale_share_uuid_column(apps, schema_editor)
        with connection.schema_editor() as schema_editor:
            migration.drop_stale_share_uuid_column(apps, schema_editor)

        with connection.cursor() as cursor:
            columns = {
                column.name
                for column in connection.introspection.get_table_description(cursor, table_name)
            }
        self.assertNotIn("share_uuid", columns)
