from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder

from apps.product.models import MockInterviewSession


SHARE_UUID_MIGRATION = "0014_mockinterviewsession_share_uuid"


def should_drop_orphan_share_uuid(column_names, applied_product_migrations):
    return "share_uuid" in column_names and SHARE_UUID_MIGRATION not in applied_product_migrations


class Command(BaseCommand):
    help = "Repair an orphan mock-interview share_uuid column before Django migrations run."

    def handle(self, *args, **options):
        table_name = MockInterviewSession._meta.db_table
        with connection.cursor() as cursor:
            columns = {
                column.name
                for column in connection.introspection.get_table_description(cursor, table_name)
            }
        applied = {
            migration
            for app, migration in MigrationRecorder(connection).applied_migrations()
            if app == "product"
        }

        if not should_drop_orphan_share_uuid(columns, applied):
            self.stdout.write("Mock interview schema preflight passed.")
            return

        quoted_table = connection.ops.quote_name(table_name)
        quoted_column = connection.ops.quote_name("share_uuid")
        with connection.cursor() as cursor:
            cursor.execute(f"ALTER TABLE {quoted_table} DROP COLUMN {quoted_column}")
        self.stdout.write(self.style.SUCCESS("Removed orphan share_uuid column before migration 0014."))
