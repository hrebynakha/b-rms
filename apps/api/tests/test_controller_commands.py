from uuid import uuid4

from django.test import TestCase, Client
from django.urls import reverse

from apps.main.models import Brewery, Controller


class ControllerCommandsTests(TestCase):
    def setUp(self):
        brewery = Brewery.objects.create(name="Test")
        self.controller = Controller.objects.create(
            brewery=brewery, name="ESP32", mac_address="esp32-test",
        )
        self.reset_url = reverse("controller-reset", args=[self.controller.pk])
        self.commands_url = reverse("controller-commands")

    def test_reset_requires_post_and_csrf(self):
        self.assertEqual(self.client.get(self.reset_url).status_code, 405)
        self.assertEqual(Client(enforce_csrf_checks=True).post(self.reset_url).status_code, 403)
        self.controller.refresh_from_db()
        self.assertIsNone(self.controller.wifi_reset_command)

    def test_command_remains_pending_until_matching_acknowledgement(self):
        self.assertEqual(self.client.post(self.reset_url).status_code, 302)
        self.controller.refresh_from_db()
        command_id = str(self.controller.wifi_reset_command)
        self.client.post(self.reset_url)
        self.controller.refresh_from_db()
        self.assertEqual(str(self.controller.wifi_reset_command), command_id)
        for _ in range(2):
            response = self.client.get(self.commands_url, {"mac_address": "esp32-test"})
            self.assertEqual(response.json()["commands"], [{"id": command_id, "type": "wifi_setup"}])
        response = self.client.post(self.commands_url, {
            "mac_address": "esp32-test", "command_id": str(uuid4()),
        }, content_type="application/json")
        self.assertEqual(response.status_code, 409)
        response = self.client.post(self.commands_url, {
            "mac_address": "esp32-test", "command_id": command_id,
        }, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        response = self.client.post(self.commands_url, {
            "mac_address": "esp32-test", "command_id": command_id,
        }, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(self.commands_url, {"mac_address": "esp32-test"}).json()["commands"], [])

    def test_invalid_and_unknown_controller(self):
        self.assertEqual(self.client.get(self.commands_url).status_code, 400)
        self.assertEqual(self.client.get(self.commands_url, {"mac_address": "unknown"}).status_code, 404)
        self.assertEqual(self.client.post(self.commands_url, {"mac_address": "esp32-test"}).status_code, 400)

    def test_dashboard_contains_confirmation_modal(self):
        response = self.client.get(reverse("brewery-list"))
        self.assertContains(response, f'id="resetControllerModal{self.controller.pk}"')
        self.assertContains(response, self.reset_url)
