from django.db import models
from django.utils.translation import gettext_lazy as _

class SensorKind(models.TextChoices):
    TEMPERATURE = "temperature", _("Temperature")
    VOLTAGE = "voltage", _("Voltage")
    WATER_LEVEL = "water_level", _("Water level")
    AMBIENT_TEMPERATURE = "ambient_temperature", _("Ambient temperature")

class Sensor(models.Model):

    class Meta:
        unique_together = ("controller", "key")

    controller = models.ForeignKey(
        "Controller",
        on_delete=models.CASCADE,
        related_name="sensors",
    )

    name = models.CharField(max_length=255)

    kind = models.CharField(
        max_length=64,
        choices=SensorKind.choices,
    )

    key = models.SlugField(max_length=64)

    unit = models.CharField(max_length=32, blank=True)

    is_enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name}"
