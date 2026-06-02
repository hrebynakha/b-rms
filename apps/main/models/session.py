from django.db import models


class BrewSessionStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class BrewSession(models.Model):
    brewery = models.ForeignKey(
        "Brewery",
        on_delete=models.CASCADE,
        related_name="brew_sessions",
    )

    recipe = models.ForeignKey(
        "Recipe",
        on_delete=models.PROTECT,
    )

    status = models.CharField(
        max_length=32,
        choices=BrewSessionStatus.choices,
        default=BrewSessionStatus.PENDING,
    )

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    current_step_index = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
