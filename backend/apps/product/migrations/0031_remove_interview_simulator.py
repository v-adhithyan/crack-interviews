from django.db import migrations


def delete_simulator_sessions(apps, schema_editor):
    simulator = apps.get_model("product", "InterviewSimulatorSession")
    session = apps.get_model("product", "MockInterviewSession")
    database = schema_editor.connection.alias

    # Deleting the shared parent also deletes its simulator row and transcript turns.
    while session_ids := list(
        simulator.objects.using(database).order_by("pk").values_list("pk", flat=True)[:500]
    ):
        session.objects.using(database).filter(pk__in=session_ids).delete()


class Migration(migrations.Migration):
    dependencies = [("product", "0030_aiintegration")]

    operations = [
        # Rolling back recreates an empty simulator table.
        migrations.RunPython(delete_simulator_sessions, migrations.RunPython.noop),
        migrations.DeleteModel(name="InterviewSimulatorSession"),
    ]
