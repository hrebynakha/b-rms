from django.db import migrations


def create_vessels(apps, schema_editor):
    Controller = apps.get_model("main", "Controller")
    Vessel = apps.get_model("main", "Vessel")
    for controller in Controller.objects.using(schema_editor.connection.alias).iterator():
        Vessel.objects.using(schema_editor.connection.alias).get_or_create(
            controller_id=controller.pk, defaults={"name": controller.name, "volume_liters": 20},
        )


class Migration(migrations.Migration):
    dependencies = [("main", "0011_brewery_location_manualcontrol_estimate_started_at_and_more")]
    operations = [migrations.RunPython(create_vessels, migrations.RunPython.noop)]
