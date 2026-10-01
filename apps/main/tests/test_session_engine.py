from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.main.models import (
    Brewery,
    Controller,
    Recipe,
    RecipeStep,
    Sensor,
    Telemetry,
)
from apps.main.models.session import BrewSession, BrewSessionMode, BrewSessionStatus
from apps.main.models.recipe import RecipeStepMode
from apps.main.services.session_engine import (
    SessionStartError,
    demo_hardware_is_ready,
    pause_session,
    refresh_session,
    resume_session,
    start_session,
)


class SessionEngineTests(TestCase):
    def setUp(self):
        self.brewery = Brewery.objects.create(name="Test Brewery")
        self.recipe = Recipe.objects.create(name="Demo Mash")
        RecipeStep.objects.create(
            recipe=self.recipe,
            order=1,
            name="Mash in",
            target_temperature=50,
            duration_minutes=20,
        )
        RecipeStep.objects.create(
            recipe=self.recipe,
            order=2,
            name="Mash rest",
            target_temperature=65,
            duration_minutes=20,
        )
        RecipeStep.objects.create(
            recipe=self.recipe,
            order=3,
            name="Mash out",
            target_temperature=78,
            duration_minutes=20,
        )
        self.session = BrewSession.objects.create(
            brewery=self.brewery,
            recipe=self.recipe,
        )
        self.controller = Controller.objects.create(
            brewery=self.brewery,
            name="Demo ESP32",
            mac_address="TEST-ESP32",
        )
        self.temperature_sensor = Sensor.objects.create(
            controller=self.controller,
            name="Mash temperature",
            kind="temperature",
            key="mash_temperature_sensor",
            unit="°C",
        )
        self.telemetry = Telemetry.objects.create(
            sensor=self.temperature_sensor,
            value=50.0,
        )

    def test_latest_temperature_wins_when_timestamps_match(self):
        newest = Telemetry.objects.create(sensor=self.temperature_sensor, value=40)
        Telemetry.objects.filter(pk=newest.pk).update(created_at=self.telemetry.created_at)
        _, progress = start_session(self.session.pk)
        self.assertEqual(progress.current_temperature, 40)
        self.assertEqual(self.session.recipe.steps.first().target_temperature, 50)
        self.assertIsNone(BrewSession.objects.get(pk=self.session.pk).step_started_at)

    def test_start_session_initializes_demo_cycle(self):
        now = timezone.now()

        session, progress = start_session(self.session.id, now=now)

        self.assertEqual(session.status, BrewSessionStatus.RUNNING)
        self.assertEqual(session.started_at, now)
        self.assertEqual(progress.step_name, "Mash in")
        self.assertEqual(progress.step_number, 1)
        self.assertEqual(progress.total_steps, 3)
        self.assertEqual(progress.step_remaining_seconds, 60)
        self.assertEqual(progress.remaining_seconds, 180)

    def test_reach_temperature_step_waits_without_starting_timer(self):
        step = self.recipe.steps.first()
        step.mode = RecipeStepMode.REACH_TEMPERATURE
        step.target_temperature = 68
        step.duration_minutes = 0
        step.save()
        Telemetry.objects.filter(pk=self.telemetry.pk).update(value=48.0)

        session, progress = start_session(self.session.id)

        self.assertEqual(session.status, BrewSessionStatus.HEATING)
        self.assertEqual(session.current_step_index, 0)
        self.assertEqual(session.step_elapsed_seconds, 0)
        self.assertIsNone(session.step_started_at)
        self.assertFalse(progress.waiting_for_temperature)
        self.assertEqual(progress.step_duration_seconds, 0)

    def test_reach_temperature_step_advances_as_soon_as_target_is_reached(self):
        step = self.recipe.steps.first()
        step.mode = RecipeStepMode.REACH_TEMPERATURE
        step.target_temperature = 68
        step.duration_minutes = 0
        step.save()
        now = timezone.now()
        self.session.status = BrewSessionStatus.HEATING
        self.session.started_at = now
        self.session.save()
        Telemetry.objects.filter(pk=self.telemetry.pk).update(value=68.0, created_at=now)

        progress = refresh_session(self.session, now=now)

        self.assertEqual(self.session.current_step_index, 1)
        self.assertEqual(progress.step_name, "Mash rest")
        self.assertEqual(self.session.step_elapsed_seconds, 0)

    def test_running_session_moves_to_next_step_after_one_minute(self):
        started_at = timezone.now() - timedelta(seconds=61)
        self.session.status = BrewSessionStatus.RUNNING
        self.session.started_at = started_at
        self.session.step_started_at = started_at
        self.session.save()

        progress = refresh_session(self.session, now=started_at + timedelta(seconds=61))

        self.assertEqual(progress.step_name, "Mash rest")
        self.assertEqual(self.session.current_step_index, 1)

    def test_next_step_waits_until_its_target_temperature_is_reached(self):
        started_at = timezone.now()
        self.session.status = BrewSessionStatus.RUNNING
        self.session.started_at = started_at
        self.session.step_started_at = started_at
        self.session.save()
        Telemetry.objects.filter(pk=self.telemetry.pk).update(
            created_at=started_at + timedelta(seconds=61), value=50.0
        )
        refresh_session(
            self.session, now=started_at + timedelta(seconds=61)
        )
        Telemetry.objects.filter(pk=self.telemetry.pk).update(value=62.0)
        waiting = refresh_session(
            self.session, now=started_at + timedelta(seconds=61)
        )

        self.assertEqual(self.session.current_step_index, 1)
        self.assertTrue(waiting.waiting_for_temperature)
        self.assertEqual(waiting.current_temperature, 62.0)
        self.assertEqual(waiting.target_temperature, 65.0)

        hot_reading = Telemetry.objects.create(
            sensor=self.temperature_sensor,
            value=65.0,
        )
        Telemetry.objects.filter(pk=hot_reading.pk).update(
            created_at=started_at + timedelta(seconds=70)
        )
        confirmed = refresh_session(
            self.session, now=started_at + timedelta(seconds=70)
        )

        self.assertFalse(confirmed.waiting_for_temperature)
        self.assertEqual(self.session.step_started_at, started_at + timedelta(seconds=70))

    def test_temperature_above_allowed_range_also_pauses_the_step(self):
        started_at = timezone.now()
        self.session.status = BrewSessionStatus.RUNNING
        self.session.started_at = started_at
        self.session.step_started_at = started_at
        self.session.save()
        Telemetry.objects.filter(pk=self.telemetry.pk).update(
            created_at=started_at + timedelta(seconds=90), value=50.0
        )
        Telemetry.objects.filter(pk=self.telemetry.pk).update(
            created_at=started_at + timedelta(seconds=10),
            value=55.0,
        )

        progress = refresh_session(
            self.session, now=started_at + timedelta(seconds=10)
        )

        self.assertEqual(self.session.status, BrewSessionStatus.WAITING)
        self.assertTrue(progress.waiting_for_temperature)
        self.assertEqual(self.session.step_elapsed_seconds, 10)

    def test_standard_mode_uses_recipe_step_minutes(self):
        started_at = timezone.now()
        self.session.mode = BrewSessionMode.STANDARD
        self.session.status = BrewSessionStatus.RUNNING
        self.session.started_at = started_at
        self.session.step_started_at = started_at
        self.session.save()
        Telemetry.objects.filter(pk=self.telemetry.pk).update(
            created_at=started_at + timedelta(seconds=60), value=50.0
        )

        progress = refresh_session(
            self.session, now=started_at + timedelta(seconds=61)
        )

        self.assertEqual(self.session.current_step_index, 0)
        self.assertEqual(progress.step_remaining_seconds, 20 * 60 - 61)

    def test_demo_time_is_split_proportionally_between_recipe_steps(self):
        self.recipe.steps.all().delete()
        RecipeStep.objects.create(
            recipe=self.recipe,
            order=1,
            name="First step",
            target_temperature=50,
            duration_minutes=30,
        )
        RecipeStep.objects.create(
            recipe=self.recipe,
            order=2,
            name="Second step",
            target_temperature=70,
            duration_minutes=30,
        )
        started_at = timezone.now()
        self.session.status = BrewSessionStatus.RUNNING
        self.session.started_at = started_at
        self.session.step_started_at = started_at
        self.session.save()

        Telemetry.objects.filter(pk=self.telemetry.pk).update(
            created_at=started_at + timedelta(seconds=90), value=50.0
        )

        before_boundary = refresh_session(
            self.session, now=started_at + timedelta(seconds=89)
        )
        at_boundary = refresh_session(
            self.session, now=started_at + timedelta(seconds=90)
        )

        self.assertEqual(before_boundary.step_name, "First step")
        self.assertEqual(before_boundary.step_remaining_seconds, 1)
        self.assertEqual(at_boundary.step_name, "Second step")
        self.assertEqual(at_boundary.step_number, 2)
        self.assertEqual(at_boundary.total_steps, 2)
        self.assertEqual(at_boundary.step_remaining_seconds, 90)
        self.assertEqual(self.session.current_step_index, 1)

    def test_demo_uses_unequal_recipe_step_durations(self):
        self.recipe.steps.all().delete()
        RecipeStep.objects.create(
            recipe=self.recipe,
            order=1,
            name="Short step",
            target_temperature=50,
            duration_minutes=10,
        )
        RecipeStep.objects.create(
            recipe=self.recipe,
            order=2,
            name="Long step",
            target_temperature=70,
            duration_minutes=20,
        )
        started_at = timezone.now()
        self.session.status = BrewSessionStatus.RUNNING
        self.session.started_at = started_at
        self.session.step_started_at = started_at
        self.session.save()

        Telemetry.objects.filter(pk=self.telemetry.pk).update(
            created_at=started_at + timedelta(seconds=60), value=50.0
        )

        progress = refresh_session(
            self.session, now=started_at + timedelta(seconds=60)
        )

        self.assertEqual(progress.step_name, "Long step")
        self.assertEqual(progress.step_remaining_seconds, 120)
        self.assertEqual(self.session.current_step_index, 1)

    def test_running_session_completes_after_three_minutes(self):
        started_at = timezone.now() - timedelta(minutes=3)
        self.session.status = BrewSessionStatus.RUNNING
        self.session.started_at = started_at
        self.session.current_step_index = 2
        self.session.step_started_at = started_at + timedelta(seconds=120)
        self.session.save()
        Telemetry.objects.filter(pk=self.telemetry.pk).update(
            created_at=started_at + timedelta(seconds=180), value=78.0
        )

        progress = refresh_session(self.session, now=started_at + timedelta(minutes=3))

        self.assertEqual(self.session.status, BrewSessionStatus.COMPLETED)
        self.assertEqual(self.session.completed_at, started_at + timedelta(minutes=3))
        self.assertEqual(progress.percent, 100)
        self.assertIsNone(progress.step_name)

    def test_paused_session_freezes_and_resumes_demo_timer(self):
        started_at = timezone.now()
        self.session.status = BrewSessionStatus.RUNNING
        self.session.started_at = started_at
        self.session.step_started_at = started_at
        self.session.save()

        _, paused_progress = pause_session(
            self.session.id, now=started_at + timedelta(seconds=30)
        )
        self.session.refresh_from_db()
        frozen_progress = refresh_session(
            self.session, now=started_at + timedelta(seconds=90)
        )
        Telemetry.objects.filter(pk=self.telemetry.pk).update(
            created_at=started_at + timedelta(seconds=90)
        )
        resume_session(self.session.id, now=started_at + timedelta(seconds=90))
        self.session.refresh_from_db()
        resumed_progress = refresh_session(
            self.session, now=started_at + timedelta(seconds=100)
        )

        self.assertEqual(paused_progress.elapsed_seconds, 30)
        self.assertEqual(frozen_progress.elapsed_seconds, 30)
        self.assertEqual(resumed_progress.elapsed_seconds, 40)
        self.assertEqual(self.session.paused_seconds, 60)

    def test_session_cannot_be_started_twice(self):
        start_session(self.session.id)

        with self.assertRaises(SessionStartError):
            start_session(self.session.id)

    def test_session_without_recipe_steps_cannot_be_started(self):
        self.recipe.steps.all().delete()

        with self.assertRaises(SessionStartError):
            start_session(self.session.id)

    def test_session_cannot_start_with_stale_demo_telemetry(self):
        stale_time = timezone.now() - timedelta(seconds=11)
        Telemetry.objects.filter(pk=self.telemetry.pk).update(created_at=stale_time)

        self.assertFalse(demo_hardware_is_ready(self.brewery))
        with self.assertRaisesMessage(SessionStartError, "No fresh telemetry"):
            start_session(self.session.id)

    def test_dashboard_shows_active_session_and_start_button(self):
        response = self.client.get(reverse("brewery-list"))

        self.assertContains(response, "Active brew session")
        self.assertContains(response, "Start 3-minute demo")
        self.assertNotContains(response, "No fresh telemetry")
        self.assertEqual(response.context["breweries"][0].active_session, self.session)

    def test_dashboard_disables_demo_when_telemetry_is_stale(self):
        stale_time = timezone.now() - timedelta(seconds=11)
        Telemetry.objects.filter(pk=self.telemetry.pk).update(created_at=stale_time)

        response = self.client.get(reverse("brewery-list"))

        self.assertContains(response, "No fresh telemetry")
        self.assertContains(response, "disabled")

    def test_pending_session_does_not_mark_first_step_as_running(self):
        response = self.client.get(
            reverse("brew-session-detail", args=[self.session.id])
        )

        self.assertFalse(response.context["step_progresses"][0]["is_current"])
        self.assertNotContains(response, "brew-step-current")
        self.assertContains(response, "Waiting to start")

    def test_session_detail_marks_completed_and_current_steps(self):
        self.session.status = BrewSessionStatus.RUNNING
        self.session.started_at = timezone.now() - timedelta(seconds=61)
        self.session.step_started_at = self.session.started_at
        self.session.save()

        response = self.client.get(
            reverse("brew-session-detail", args=[self.session.id])
        )

        self.assertEqual(response.context["session"].current_step_index, 1)
        self.assertTrue(response.context["step_progresses"][0]["is_completed"])
        self.assertContains(response, "brew-step-completed", count=1)
        self.assertContains(response, "brew-step-current", count=1)
        self.assertContains(response, "Waiting for temperature")

    def test_session_detail_warns_when_temperature_is_below_target(self):
        self.session.status = BrewSessionStatus.RUNNING
        self.session.started_at = timezone.now()
        self.session.save()
        Telemetry.objects.create(sensor=self.temperature_sensor, value=40.0)

        response = self.client.get(
            reverse("brew-session-detail", args=[self.session.id])
        )

        self.assertContains(response, "outside the allowed range")
        self.assertContains(response, "session-temperature-chart")

    def test_completed_session_can_be_deleted(self):
        self.session.status = BrewSessionStatus.COMPLETED
        self.session.completed_at = timezone.now()
        self.session.save()

        response = self.client.post(
            reverse("brew-session-delete"),
            {"session_id": self.session.id},
        )

        self.assertRedirects(response, reverse("brew-session-list"))
        self.assertFalse(BrewSession.objects.filter(pk=self.session.id).exists())

    def test_sensor_cleanup_can_keep_recent_minutes(self):
        Telemetry.objects.filter(pk=self.telemetry.pk).update(
            created_at=timezone.now() - timedelta(minutes=10)
        )
        Telemetry.objects.create(sensor=self.temperature_sensor, value=63.0)

        response = self.client.post(
            reverse("sensor-cleanup", args=[self.temperature_sensor.id]),
            {"strategy": "minutes", "amount": 5},
        )

        self.assertRedirects(
            response,
            reverse("sensor-detail", args=[self.temperature_sensor.id]),
        )
        self.assertEqual(self.temperature_sensor.telemetry.count(), 1)

    def test_sensor_cleanup_can_keep_last_session_time_window(self):
        now = timezone.now()
        self.session.status = BrewSessionStatus.COMPLETED
        self.session.started_at = now - timedelta(minutes=5)
        self.session.completed_at = now - timedelta(minutes=2)
        self.session.save()
        Telemetry.objects.filter(pk=self.telemetry.pk).update(
            created_at=now - timedelta(minutes=10)
        )
        kept = Telemetry.objects.create(sensor=self.temperature_sensor, value=64.0)
        Telemetry.objects.filter(pk=kept.pk).update(
            created_at=now - timedelta(minutes=3)
        )

        self.client.post(
            reverse("sensor-cleanup", args=[self.temperature_sensor.id]),
            {"strategy": "sessions", "amount": 1},
        )

        self.assertEqual(
            list(self.temperature_sensor.telemetry.values_list("id", flat=True)),
            [kept.id],
        )
