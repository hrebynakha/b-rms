from django.db import models


class Telemetry(models.Model):
    class Meta:
        ordering = ["-created_at"]

    sensor = models.ForeignKey(
        "Sensor",
        on_delete=models.CASCADE,
        related_name="telemetry",
    )

    value = models.FloatField()

    created_at = models.DateTimeField(
        auto_now_add=True,
    )
