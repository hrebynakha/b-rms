from uuid import uuid4

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.main.models import Brewery, Controller, Recipe
from apps.main.models.session import BrewSession


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

    def test_buzzer_state_tracks_latest_started_session_and_step(self):
        def state():
            return self.client.get(self.commands_url, {"mac_address": "esp32-test"}).json()["brew_session"]

        self.assertIsNone(state())
        recipe = Recipe.objects.create(name="Buzzer test")
        session = BrewSession.objects.create(
            brewery=self.controller.brewery, recipe=recipe,
            started_at=timezone.now(), status="running",
        )
        # A pending session must not hide the currently running session.
        BrewSession.objects.create(brewery=self.controller.brewery, recipe=recipe)
        self.assertEqual(state(), {"id": session.pk, "step_index": 0, "status": "running"})
        session.current_step_index = 1
        session.save(update_fields=["current_step_index"])
        for _ in range(2):
            self.assertEqual(state()["step_index"], 1)
        other = Brewery.objects.create(name="Other brewery")
        BrewSession.objects.create(brewery=other, recipe=recipe, started_at=timezone.now())
        self.assertEqual(state()["id"], session.pk)

    def test_dashboard_contains_confirmation_modal(self):
        response = self.client.get(reverse("brewery-list"))
        self.assertContains(response, f'id="resetControllerModal{self.controller.pk}"')
        self.assertContains(response, self.reset_url)

    def test_rgb_reports_pending_session_and_lifecycle(self):
        recipe = Recipe.objects.create(name="RGB test")
        session = BrewSession.objects.create(brewery=self.controller.brewery, recipe=recipe)

        def state():
            response = self.client.get(self.commands_url, {"mac_address": "esp32-test"})
            self.assertEqual(response.status_code, 200)
            return response.json()["brew_session"]

        self.assertEqual(state(), {"id": session.pk, "step_index": 0, "status": "pending"})
        session.started_at = timezone.now()
        session.save(update_fields=["started_at"])
        for value in ("running", "heating", "waiting_temperature", "paused", "completed", "failed", "cancelled"):
            session.status = value
            session.save(update_fields=["status"])
            self.assertEqual(state()["status"], value)

        # A new draft replaces a terminal session, but never an active one.
        draft = BrewSession.objects.create(brewery=self.controller.brewery, recipe=recipe)
        self.assertEqual(state()["id"], draft.pk)
        session.status = "paused"
        session.save(update_fields=["status"])
        self.assertEqual(state()["id"], session.pk)
