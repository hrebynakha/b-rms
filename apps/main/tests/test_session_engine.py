from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.main.models import Brewery, Recipe
from apps.main.models.session import BrewSession, BrewSessionStatus
from apps.main.services.session_engine import (
    SessionStartError,
    refresh_session,
    start_session,
)


class SessionEngineTests(TestCase):
    def setUp(self):
        self.brewery = Brewery.objects.create(name="Test Brewery")
        self.recipe = Recipe.objects.create(name="Demo Mash")
        self.session = BrewSession.objects.create(
            brewery=self.brewery,
            recipe=self.recipe,
        )

    def test_start_session_initializes_demo_cycle(self):
        now = timezone.now()

        session, progress = start_session(self.session.id, now=now)

        self.assertEqual(session.status, BrewSessionStatus.RUNNING)
        self.assertEqual(session.started_at, now)
        self.assertEqual(progress.step_name, "Mash in")
        self.assertEqual(progress.remaining_seconds, 180)

    def test_running_session_moves_to_next_step_after_one_minute(self):
        started_at = timezone.now() - timedelta(seconds=61)
        self.session.status = BrewSessionStatus.RUNNING
        self.session.started_at = started_at
        self.session.save()

        progress = refresh_session(self.session, now=started_at + timedelta(seconds=61))

        self.assertEqual(progress.step_name, "Mash rest")
        self.assertEqual(self.session.current_step_index, 1)

    def test_running_session_completes_after_three_minutes(self):
        started_at = timezone.now() - timedelta(minutes=3)
        self.session.status = BrewSessionStatus.RUNNING
        self.session.started_at = started_at
        self.session.save()

        progress = refresh_session(self.session, now=started_at + timedelta(minutes=3))

        self.assertEqual(self.session.status, BrewSessionStatus.COMPLETED)
        self.assertEqual(self.session.completed_at, started_at + timedelta(minutes=3))
        self.assertEqual(progress.percent, 100)
        self.assertIsNone(progress.step_name)

    def test_session_cannot_be_started_twice(self):
        start_session(self.session.id)

        with self.assertRaises(SessionStartError):
            start_session(self.session.id)

    def test_dashboard_shows_active_session_and_start_button(self):
        response = self.client.get(reverse("brewery-list"))

        self.assertContains(response, "Active brew session")
        self.assertContains(response, "Start 3-minute demo")
        self.assertEqual(response.context["breweries"][0].active_session, self.session)
