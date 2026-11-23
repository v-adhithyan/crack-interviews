from uuid import uuid4

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase
from django.urls import Resolver404, resolve


class RemovedSimulatorRoutesTests(SimpleTestCase):
    def test_legacy_simulator_routes_no_longer_resolve(self):
        room = f"{uuid4()}/"
        paths = ["", "history/", room] + [
            f"{room}{action}/"
            for action in ("reuse", "pause", "state", "token", "turns", "finish", "feedback")
        ]
        for path in paths:
            with self.subTest(path=path), self.assertRaises(Resolver404):
                resolve(f"/app/interview-simulator/{path}")


class RemoveSimulatorMigrationTests(TransactionTestCase):
    def test_migration_deletes_simulator_history_and_keeps_system_design(self):
        before = [("product", "0030_aiintegration")]
        after = [("product", "0031_remove_interview_simulator")]
        executor = MigrationExecutor(connection)
        self.addCleanup(self.restore_schema, executor.loader.graph.leaf_nodes())
        executor.migrate(before)
        old_apps = executor.loader.project_state(before).apps

        user = old_apps.get_model("auth", "User").objects.create(username="migration-user")
        session_model = old_apps.get_model("product", "MockInterviewSession")
        simulator_model = old_apps.get_model("product", "InterviewSimulatorSession")
        turn_model = old_apps.get_model("product", "MockInterviewTurn")
        system_design = session_model.objects.create(user=user, topic="System design")
        simulator = simulator_model.objects.create(
            user=user, topic="Simulator", resume_text="Private resume snapshot"
        )
        system_turn = turn_model.objects.create(session=system_design, role="user", text="Design answer")
        turn_model.objects.create(session=simulator, role="user", text="Simulator answer")

        executor = MigrationExecutor(connection)
        executor.migrate(after)
        self.assertEqual(list(session_model.objects.values_list("pk", flat=True)), [system_design.pk])
        self.assertEqual(list(turn_model.objects.values_list("pk", flat=True)), [system_turn.pk])
        self.assertNotIn(simulator_model._meta.db_table, connection.introspection.table_names())

    def restore_schema(self, targets):
        MigrationExecutor(connection).migrate(targets)
