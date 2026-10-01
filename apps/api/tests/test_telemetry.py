from django.test import TestCase
from django.urls import reverse

from apps.main.models import Brewery, Controller, Sensor, Telemetry


class TelemetryTests(TestCase):
    def setUp(self):
        brewery = Brewery.objects.create(name="Test brewery")
        self.controller = Controller.objects.create(
            brewery=brewery, name="ESP", mac_address="telemetry-test",
        )
        self.sensor = Sensor.objects.create(
            controller=self.controller, name="Temperature", kind="temperature",
            key="mash_temperature_sensor",
        )
        self.url = reverse("telemetry")

    def post_metrics(self, metrics, device="telemetry-test"):
        return self.client.post(self.url, {"mac_address": device, "metrics": metrics},
                                content_type="application/json")

    def test_nonfinite_metrics_are_rejected_without_partial_writes(self):
        for value in ["NaN", "Infinity", "-Infinity"]:
            with self.subTest(value=value):
                response = self.post_metrics({"mash_temperature_sensor": 45, "other": value})
                self.assertEqual(response.status_code, 400)
                self.assertFalse(Telemetry.objects.exists())
                self.controller.refresh_from_db()
                self.assertIsNone(self.controller.last_seen_at)

    def test_unknown_controller_returns_not_found(self):
        self.assertEqual(self.post_metrics({"mash_temperature_sensor": 45}, "unknown").status_code, 404)

    def test_known_metrics_are_saved_and_unknown_keys_are_ignored(self):
        self.assertEqual(self.post_metrics({"mash_temperature_sensor": 45, "unknown": 12}).status_code, 200)
        reading = Telemetry.objects.get()
        self.assertEqual(reading.sensor, self.sensor)
        self.assertEqual(reading.value, 45)
        self.assertIsNotNone(reading.created_at)
