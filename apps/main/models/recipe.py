from django.db import models
from django.utils.translation import gettext_lazy as _


class RecipeStepMode(models.TextChoices):
    REACH_TEMPERATURE = "reach_temperature", _("Reach temperature")
    HOLD_TEMPERATURE = "hold_temperature", _("Temperature hold")


class Recipe(models.Model):
    name = models.CharField(max_length=255)

    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name}"


class RecipeStep(models.Model):
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="steps",
    )

    order = models.PositiveIntegerField()

    name = models.CharField(max_length=255)

    target_temperature = models.FloatField()

    mode = models.CharField(
        max_length=32,
        choices=RecipeStepMode.choices,
        default=RecipeStepMode.HOLD_TEMPERATURE,
    )

    duration_minutes = models.PositiveIntegerField()

    class Meta:
        ordering = ["order"]
