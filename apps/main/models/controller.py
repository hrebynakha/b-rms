from django.db import models
from django.utils import timezone

class Controller(models.Model):
    brewery = models.ForeignKey(
        "Brewery",
        on_delete=models.CASCADE,
        related_name="controllers",
    )

    name = models.CharField(max_length=255)

    mac_address = models.CharField(
        max_length=255,
        unique=True,
    )

    firmware_version = models.CharField(
        max_length=64,
        blank=True,
    )

    last_seen_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    is_enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name}"

    @property
    def is_online(self):
        if not self.last_seen_at:
            return False

        return (
            timezone.now() - self.last_seen_at
        ).total_seconds() < 30
