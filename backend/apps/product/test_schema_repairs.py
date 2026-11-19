import importlib
from io import StringIO
from unittest.mock import patch

from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase

from .models import MockInterviewSession
from .management.commands.repair_mock_interview_schema import (
    SHARE_UUID_MIGRATION,
    PRODUCT_SCALE_MIGRATION,
    should_drop_orphan_share_uuid,
)


class MockInterviewSchemaRepairTests(TransactionTestCase):
    def test_pre_migration_repair_only_drops_an_orphan_column(self):
        self.assertTrue(should_drop_orphan_share_uuid({"id", "share_uuid"}, {"0013_previous"}))
        self.assertFalse(should_drop_orphan_share_uuid({"id"}, {"0013_previous"}))
        self.assertFalse(should_drop_orphan_share_uuid({"id", "share_uuid"}, {SHARE_UUID_MIGRATION}))

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

    def test_retired_product_scale_schema_cleanup_preserves_sessions_and_is_repeatable(self):
        user = get_user_model().objects.create_user('schema-test')
        session = MockInterviewSession.objects.create(user=user, topic='Saved interview')
        table = connection.ops.quote_name(MockInterviewSession._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN track varchar(24) NOT NULL DEFAULT 'product_scale'")
        recorder = MigrationRecorder(connection)
        recorder.record_applied('product', PRODUCT_SCALE_MIGRATION)

        for _ in range(2):
            call_command('repair_mock_interview_schema', stdout=StringIO())
        with connection.cursor() as cursor:
            columns = {c.name for c in connection.introspection.get_table_description(cursor, MockInterviewSession._meta.db_table)}
        self.assertNotIn('track', columns)
        self.assertNotIn(('product', PRODUCT_SCALE_MIGRATION), recorder.applied_migrations())
        session.refresh_from_db()
        self.assertEqual(session.topic, 'Saved interview')
        MockInterviewSession.objects.create(user=user, topic='New interview')

    def test_cleanup_recovers_when_column_removed_but_migration_record_remains(self):
        recorder = MigrationRecorder(connection)
        recorder.record_applied('product', PRODUCT_SCALE_MIGRATION)
        call_command('repair_mock_interview_schema', stdout=StringIO())
        self.assertNotIn(('product', PRODUCT_SCALE_MIGRATION), recorder.applied_migrations())

    def test_fresh_database_preflight_does_not_require_interview_table(self):
        with patch.object(connection.introspection, 'table_names', return_value=[]):
            output = StringIO()
            call_command('repair_mock_interview_schema', stdout=output)
        self.assertIn('migrations will create it', output.getvalue())
