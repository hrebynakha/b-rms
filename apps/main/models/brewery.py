from django.db import models
from django.utils.text import slugify


class Brewery(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)

    description = models.TextField(blank=True)
    location = models.CharField(max_length=255, blank=True)

    is_enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self) -> str:
        return f"{self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = (slugify(self.name) or "brewery")[:40]
            self.slug = base
            suffix = 2
            while Brewery.objects.exclude(pk=self.pk).filter(slug=self.slug).exists():
                self.slug = f"{base[:40]}-{suffix}"
                suffix += 1
        super().save(*args, **kwargs)
