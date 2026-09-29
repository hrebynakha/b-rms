from django.test import TestCase
from django.urls import reverse

from apps.main.models import Brewery, Recipe
from apps.main.models.session import BrewSession, BrewSessionStatus


class BrewSessionStartApiTests(TestCase):
    def setUp(self):
        brewery = Brewery.objects.create(name="API Brewery")
        recipe = Recipe.objects.create(name="API Demo")
        self.session = BrewSession.objects.create(brewery=brewery, recipe=recipe)
        self.url = reverse("api-brew-session-start", args=[self.session.id])

    def test_start_endpoint_starts_pending_session(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, BrewSessionStatus.RUNNING)
        self.assertEqual(response.json()["current_step"], "Mash in")
        self.assertEqual(response.json()["remaining_seconds"], 180)

    def test_start_endpoint_returns_conflict_for_running_session(self):
        self.client.post(self.url)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 409)

    def test_start_endpoint_returns_not_found(self):
        response = self.client.post(
            reverse("api-brew-session-start", args=[999999])
        )

        self.assertEqual(response.status_code, 404)

