from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class Vessel(models.Model):
    """One controlled vessel per ESP; its brewery is defined by the controller."""
    controller = models.OneToOneField("Controller", on_delete=models.CASCADE, related_name="vessel")
    name = models.CharField(max_length=255)
    volume_liters = models.DecimalField(
        max_digits=7, decimal_places=1, default=20,
        validators=[MinValueValidator(0.1), MaxValueValidator(100000)],
    )

    def __str__(self):
        return self.name
