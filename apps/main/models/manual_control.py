from django.db import models


class ManualControl(models.Model):
    controller = models.OneToOneField("Controller", on_delete=models.CASCADE, related_name="manual_control")
    target_temperature = models.FloatField(default=50)
    active = models.BooleanField(default=False)
    warning_delta = models.FloatField(default=10)
    warning_mode = models.CharField(max_length=10, default="degrees")
    revision = models.PositiveIntegerField(default=0)
    reported_revision = models.PositiveIntegerField(null=True, blank=True)
    reported_power = models.FloatField(default=0)
    reported_at = models.DateTimeField(null=True, blank=True)
    reported_output_mode = models.CharField(max_length=16, blank=True)
    measured_voltage = models.FloatField(null=True, blank=True)


class ManualControlSample(models.Model):
    control = models.ForeignKey(ManualControl, on_delete=models.CASCADE, related_name="samples")
    temperature = models.FloatField(null=True)
    target_temperature = models.FloatField()
    power_percent = models.FloatField()
    signal_voltage = models.FloatField()
    measured_voltage = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
