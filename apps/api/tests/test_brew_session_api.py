from django.test import TestCase
from django.urls import reverse

from apps.main.models import Brewery, Controller, Recipe, RecipeStep, Sensor, Telemetry
from apps.main.models.session import BrewSession, BrewSessionStatus


class BrewSessionStartApiTests(TestCase):
    def setUp(self):
        brewery = Brewery.objects.create(name="API Brewery")
        recipe = Recipe.objects.create(name="API Demo")
        RecipeStep.objects.create(
            recipe=recipe,
            order=1,
            name="Mash in",
            target_temperature=50,
            duration_minutes=60,
        )
        self.session = BrewSession.objects.create(brewery=brewery, recipe=recipe)
        controller = Controller.objects.create(
            brewery=brewery,
            name="Demo ESP32",
            mac_address="API-ESP32",
        )
        sensor = Sensor.objects.create(
            controller=controller,
            name="Mash temperature",
            kind="temperature",
            key="mash_temperature_sensor",
            unit="°C",
        )
        self.telemetry = Telemetry.objects.create(sensor=sensor, value=50.0)
        self.url = reverse("api-brew-session-start", args=[self.session.id])

    def test_start_endpoint_starts_pending_session(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, BrewSessionStatus.RUNNING)
        self.assertEqual(response.json()["current_step"], "Mash in")
        self.assertEqual(response.json()["current_step_number"], 1)
        self.assertEqual(response.json()["total_steps"], 1)
        self.assertEqual(response.json()["step_remaining_seconds"], 180)
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

    def test_start_endpoint_rejects_inactive_demo_scripts(self):
        self.telemetry.delete()

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 409)
        self.assertIn("Demo scripts are inactive", response.json()["detail"])

    def test_session_can_be_paused_and_resumed(self):
        self.client.post(self.url)

        pause_response = self.client.post(
            reverse("api-brew-session-pause", args=[self.session.id])
        )
        self.session.refresh_from_db()
        self.assertEqual(pause_response.status_code, 200)
        self.assertEqual(self.session.status, BrewSessionStatus.PAUSED)

        resume_response = self.client.post(
            reverse("api-brew-session-resume", args=[self.session.id])
        )
        self.session.refresh_from_db()
        self.assertEqual(resume_response.status_code, 200)
        self.assertEqual(self.session.status, BrewSessionStatus.RUNNING)

    def test_operator_can_override_temperature_wait(self):
        self.telemetry.value = 40.0
        self.telemetry.save(update_fields=["value"])
        self.client.post(self.url)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, BrewSessionStatus.WAITING)

        response = self.client.post(
            reverse(
                "api-brew-session-temperature-override",
                args=[self.session.id],
            )
        )

        self.session.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.session.status, BrewSessionStatus.RUNNING)
        self.assertTrue(self.session.temperature_override)
