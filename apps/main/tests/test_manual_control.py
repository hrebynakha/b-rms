from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
import json
import re

from apps.main.models import Brewery, Controller, Sensor, Telemetry, ManualControl
from apps.main.services.manual_control import control_state, update_from_telemetry
from apps.main.models import Recipe, BrewSession
from apps.main.models.session import BrewSessionStatus
from apps.main.services.session_engine import start_session, SessionStartError


class ManualControlTests(TestCase):
    def setUp(self):
        self.brewery = Brewery.objects.create(name="Test")
        self.controller = Controller.objects.create(brewery=self.brewery, name="ESP", mac_address="esp-test")
        self.sensor = Sensor.objects.create(controller=self.controller, key="mash_temperature_sensor", name="Temperature", kind="temperature")
        self.control = ManualControl.objects.create(controller=self.controller)
        self.action_url = reverse("manual-action", args=[self.controller.pk])
        self.status_url = reverse("manual-status", args=[self.controller.pk])

    def reading(self, value):
        return Telemetry.objects.create(sensor=self.sensor, value=value)

    def test_server_does_not_invent_pid_duty_or_gpio_state(self):
        self.control.active = True
        for temperature, power in [(30, 100), (40, 100), (45, 50), (49, 10), (50, 0), (55, 0)]:
            self.reading(temperature)
            state = control_state(self.control)
            self.assertIsNone(state["power_percent"])
            self.assertIsNone(state["signal_voltage"])

    def test_overheat_latches_stop_and_requires_restart(self):
        self.control.active = True
        self.control.save()
        self.reading(60)
        update_from_telemetry(self.controller)
        self.control.refresh_from_db()
        self.assertFalse(self.control.active)
        self.assertTrue(control_state(self.control)["overheat"])
        self.assertEqual(self.client.post(self.action_url, {"action": "start"}).status_code, 409)
        self.reading(45)
        self.assertIsNone(control_state(self.control)["power_percent"])
        self.assertEqual(self.client.post(self.action_url, {"action": "start"}).status_code, 200)

    def test_stop_retains_temperature_and_warns_about_overshoot(self):
        self.reading(45)
        self.client.post(self.action_url, {"action": "start"})
        response = self.client.post(self.action_url, {"action": "stop", "target_temperature": "invalid"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["power_percent"])
        self.reading(62)
        state = self.client.get(self.status_url).json()
        self.assertFalse(state["active"])
        self.assertTrue(state["overheat"])
        self.assertEqual(state["delta"], 17)

    def test_percent_warning_and_missing_data(self):
        self.control.warning_mode = "percent"
        self.control.warning_delta = 10
        self.control.active = True
        self.reading(55)
        self.assertTrue(control_state(self.control)["overheat"])
        self.assertEqual(control_state(self.control)["warning_temperature"], 55)
        Telemetry.objects.all().delete()
        self.assertIsNone(control_state(self.control)["power_percent"])
        self.assertEqual(self.client.post(self.action_url, {"action": "start"}).status_code, 409)

    def test_stale_data_stops_mode_and_blocks_start(self):
        reading = self.reading(40)
        Telemetry.objects.filter(pk=reading.pk).update(created_at=timezone.now() - timedelta(seconds=11))
        self.control.active = True
        self.control.save()
        state = self.client.get(self.status_url).json()
        self.assertFalse(state["active"])
        self.assertIsNone(state["power_percent"])
        self.assertFalse(state["live"])
        self.assertEqual(self.client.post(self.action_url, {"action": "start"}).status_code, 409)

    def test_validation_csrf_and_rendering(self):
        self.assertEqual(self.client.get(self.action_url).status_code, 405)
        self.assertEqual(Client(enforce_csrf_checks=True).post(self.action_url, {"action": "stop"}).status_code, 403)
        for data in [{"action": "start", "target_temperature": 101}, {"action": "apply", "target_temperature": "NaN"}, {"action": "apply", "warning_delta": 0}]:
            self.assertEqual(self.client.post(self.action_url, data).status_code, 400)
        response = self.client.get(reverse("manual-control", args=[self.controller.pk]))
        self.assertContains(response, 'id="manual-stop"')
        self.assertContains(response, 'id="manual-chart"')

    def test_commands_deliver_pwm_and_telemetry_confirms_it(self):
        self.reading(45)
        self.client.post(self.action_url, {"action": "start"})
        state = self.client.get(reverse("controller-commands"), {"mac_address": "esp-test"}).json()["manual_control"]
        self.assertIsNone(state["power_percent"])
        self.assertEqual(state["pid"], {"kp": 10, "ki": .1, "kd": 5})
        self.assertEqual(state["window_ms"], 2000)
        self.assertFalse(state["simulation"])
        self.assertEqual(state["output_mode"], "time_pwm")
        response = self.client.post(reverse("telemetry"), {
            "mac_address": "esp-test", "metrics": {"mash_temperature_sensor": 48},
            "manual_control": {"revision": state["revision"], "power_percent": 50,
                               "output_mode": "time_pwm", "feedback_enabled": True, "measured_voltage": 3.25,
                               "ssr_on": True, "window_ms": 2000, "on_time_ms": 1000, "enabled": True},
        }, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        state = self.client.get(self.status_url).json()
        self.assertEqual(state["reported_power"], 50)
        self.assertEqual(state["power_percent"], 50)
        self.assertIsNotNone(state["reported_at"])
        self.assertEqual(state["history"][-1]["voltage"], 3.3)
        self.assertTrue(state["ssr_on"])
        self.assertTrue(state["output_confirmed"])
        self.assertEqual(state["on_time_ms"], 1000)
        self.assertEqual(state["measured_voltage"], 3.25)
        self.assertEqual(state["history"][-1]["measured_voltage"], 3.25)
        self.assertEqual(state["reported_output_mode"], "time_pwm")

    def test_feedback_is_optional_and_finite(self):
        self.reading(45)
        url = reverse("telemetry")
        payload = {"mac_address": "esp-test", "metrics": {},
                   "manual_control": {"revision": 0, "power_percent": 0, "output_mode": "pwm", "feedback_enabled": False, "measured_voltage": 2}}
        self.assertEqual(self.client.post(url, payload, content_type="application/json").status_code, 200)
        self.assertIsNone(self.client.get(self.status_url).json()["measured_voltage"])
        for value in ["NaN", -1, 5]:
            payload["manual_control"]["measured_voltage"] = value
            self.assertEqual(self.client.post(url, payload, content_type="application/json").status_code, 400)

    def test_manual_ui_and_errors_follow_selected_language(self):
        url = reverse("manual-control", args=[self.controller.pk])
        for language, title, chart_label, error in [
            ("en", "Temperature control panel", "Sensor °C", "Fresh sensor readings"),
            ("uk", "Пульт керування температурою", "Датчик °C", "Потрібні свіжі показники"),
        ]:
            with self.subTest(language=language):
                response = self.client.get(url, HTTP_ACCEPT_LANGUAGE=language)
                self.assertContains(response, title)
                script = re.search(r'<script id="manual-messages" type="application/json">(.*?)</script>', response.content.decode(), re.S)
                self.assertEqual(json.loads(script.group(1))["sensor_chart"], chart_label)
                self.assertContains(response, 'step="1"', count=3)
                self.assertContains(response, 'value="50"')
                response = self.client.post(self.action_url, {"action": "start"}, HTTP_ACCEPT_LANGUAGE=language)
                self.assertIn(error, response.json()["detail"])

    def test_fractional_settings_are_rejected(self):
        for field in ("target_temperature", "warning_delta"):
            response = self.client.post(self.action_url, {"action": "apply", field: 40.5})
            self.assertEqual(response.status_code, 400)

    def test_chart_refresh_excludes_old_samples_without_deleting_history(self):
        self.reading(40)
        applied = self.client.post(self.action_url, {"action": "apply"}).json()
        self.assertIn("chart_since", applied)
        self.assertEqual(len(self.client.get(self.status_url).json()["history"]), 1)
        # Windows can return identical clock timestamps for adjacent requests.
        sample_time = self.control.samples.get().created_at
        with patch("apps.main.manual_views.timezone.now", return_value=sample_time):
            response = self.client.get(self.status_url, {"reset_chart": "1"}).json()
        self.assertIn("chart_since", response)
        self.assertEqual(response["history"], [])
        self.assertEqual(self.control.samples.count(), 1)

    def test_stop_button_is_disabled_until_mode_is_started(self):
        url = reverse("manual-control", args=[self.controller.pk])
        response = self.client.get(url)
        self.assertRegex(response.content.decode(), r'id="manual-stop"\s+disabled')
        self.reading(40)
        self.client.post(self.action_url, {"action": "start"})
        response = self.client.get(url)
        self.assertNotRegex(response.content.decode(), r'id="manual-stop"\s+disabled')

    def test_reset_disables_output(self):
        self.reading(40)
        self.client.post(self.action_url, {"action": "start"})
        self.client.post(reverse("controller-reset", args=[self.controller.pk]))
        state = self.client.get(self.status_url).json()
        self.assertFalse(state["active"])
        self.assertIsNone(state["power_percent"])

    def test_pid_settings_validation_and_fault_stop(self):
        self.reading(45)
        for field, value in [("pid_kp", 101), ("pid_ki", 11), ("pid_kd", "NaN"), ("window_ms", 999)]:
            response = self.client.post(self.action_url, {"action": "apply", field: value})
            self.assertEqual(response.status_code, 400)
        response = self.client.post(self.action_url, {"action": "start", "pid_kp": 8, "pid_ki": .2, "pid_kd": 2, "window_ms": 4000})
        state = response.json()
        self.assertEqual(state["pid"], {"kp": 8, "ki": .2, "kd": 2})
        self.assertEqual(state["window_ms"], 4000)
        response = self.client.post(reverse("telemetry"), {
            "mac_address": "esp-test", "metrics": {"mash_temperature_sensor": 46},
            "manual_control": {"revision": state["revision"], "power_percent": 0, "output_mode": "time_pwm",
                               "ssr_on": False, "window_ms": 4000, "on_time_ms": 0, "enabled": False, "fault": True},
        }, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.control.refresh_from_db()
        self.assertFalse(self.control.active)
        self.assertEqual(self.control.revision, state["revision"] + 1)

    def test_inconsistent_time_pwm_report_is_rejected(self):
        report = {"revision": 0, "power_percent": 25, "output_mode": "time_pwm",
                  "ssr_on": False, "window_ms": 2000, "on_time_ms": 500, "enabled": True}
        for changes in [{"on_time_ms": 2500}, {"on_time_ms": 1000}, {"enabled": False}, {"window_ms": 0}]:
            response = self.client.post(reverse("telemetry"), {"mac_address": "esp-test", "metrics": {},
                "manual_control": {**report, **changes}}, content_type="application/json")
            self.assertEqual(response.status_code, 400)

    def test_manual_and_recipe_modes_are_exclusive(self):
        self.reading(40)
        recipe = Recipe.objects.create(name="Test recipe")
        session = BrewSession.objects.create(brewery=self.brewery, recipe=recipe, status=BrewSessionStatus.WAITING)
        self.assertEqual(self.client.post(self.action_url, {"action": "start"}).status_code, 409)
        session.status = BrewSessionStatus.PENDING
        session.save()
        self.assertEqual(self.client.post(self.action_url, {"action": "start"}).status_code, 200)
        with self.assertRaises(SessionStartError):
            start_session(session.pk)
