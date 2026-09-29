from django.db import models
from django.utils.translation import gettext_lazy as _


class BrewSessionStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    RUNNING = "running", _("Running")
    PAUSED = "paused", _("Paused")
    COMPLETED = "completed", _("Completed")
    FAILED = "failed", _("Failed")


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
    paused_at = models.DateTimeField(null=True, blank=True)
    paused_seconds = models.PositiveIntegerField(default=0)

    current_step_index = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
