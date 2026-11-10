from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder

from apps.product.models import MockInterviewSession


PRODUCT_SCALE_MIGRATION = "0029_mockinterviewsession_track"

SHARE_UUID_MIGRATION = "0014_mockinterviewsession_share_uuid"


def should_drop_orphan_share_uuid(column_names, applied_product_migrations):
    return "share_uuid" in column_names and SHARE_UUID_MIGRATION not in applied_product_migrations


class Command(BaseCommand):
    help = "Repair legacy mock-interview columns before Django migrations run."

    def handle(self, *args, **options):
        table_name = MockInterviewSession._meta.db_table
        with connection.cursor() as cursor:
            if table_name not in connection.introspection.table_names(cursor):
                self.stdout.write("Mock interview table not created yet; migrations will create it.")
                return
            columns = {
                column.name
                for column in connection.introspection.get_table_description(cursor, table_name)
            }
        applied = {
            migration
            for app, migration in MigrationRecorder(connection).applied_migrations()
            if app == "product"
        }

        quoted_table = connection.ops.quote_name(table_name)
        if should_drop_orphan_share_uuid(columns, applied):
            quoted_column = connection.ops.quote_name("share_uuid")
            with connection.cursor() as cursor:
                cursor.execute(f"ALTER TABLE {quoted_table} DROP COLUMN {quoted_column}")
            self.stdout.write(self.style.SUCCESS("Removed orphan share_uuid column before migration 0014."))

        # The product-scale feature and its migration were reverted. An existing
        # NOT NULL track column would reject inserts from the restored model.
        # Check the actual schema so retries also recover from interrupted DDL.
        if "track" in columns:
            quoted_column = connection.ops.quote_name("track")
            with connection.cursor() as cursor:
                cursor.execute(f"ALTER TABLE {quoted_table} DROP COLUMN {quoted_column}")
            self.stdout.write(self.style.SUCCESS("Removed retired product-scale track column; interview sessions preserved."))

        # Only forget the removed migration after its column is gone. Repeating
        # this step is safe if a previous deployment stopped after the DDL.
        if PRODUCT_SCALE_MIGRATION in applied:
            MigrationRecorder(connection).record_unapplied("product", PRODUCT_SCALE_MIGRATION)
            self.stdout.write(self.style.SUCCESS("Cleared retired product-scale migration record."))

        self.stdout.write("Mock interview schema preflight passed.")
