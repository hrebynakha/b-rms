from django.db import migrations, models


def pause_legacy_controls(apps, schema_editor):
    Control = apps.get_model("main", "ManualControl")
    Control.objects.using(schema_editor.connection.alias).filter(active=True).update(
        active=False, revision=models.F("revision") + 1,
    )


class Migration(migrations.Migration):
    dependencies = [("main", "0013_manualcontrol_pid_kd_manualcontrol_pid_ki_and_more")]
    operations = [migrations.RunPython(pause_legacy_controls, migrations.RunPython.noop)]
