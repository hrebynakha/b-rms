from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("main", "0007_recipestep_mode_alter_brewsession_status")]
    operations = [
        migrations.AddField(
            model_name="controller", name="wifi_reset_command",
            field=models.UUIDField(blank=True, null=True),
        ),
    ]
