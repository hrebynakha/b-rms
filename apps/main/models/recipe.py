from django.db import models


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

    duration_minutes = models.PositiveIntegerField()

    class Meta:
        ordering = ["order"]
