from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import override

from apps.main.models import Brewery, Recipe, RecipeStep
from apps.main.models.session import BrewSession, BrewSessionStatus
from apps.main.services.session_engine import (
    SessionStateError,
    cancel_session,
    refresh_session,
    resume_session,
    start_session,
    SessionStartError,
)


class SessionCancelTests(TestCase):
    def setUp(self):
        self.brewery = Brewery.objects.create(name="Brewery")
        self.recipe = Recipe.objects.create(name="Recipe")
        RecipeStep.objects.create(
            recipe=self.recipe,
            order=1,
            name="Mash",
            target_temperature=65,
            duration_minutes=30,
        )
        self.session = BrewSession.objects.create(
            brewery=self.brewery,
            recipe=self.recipe,
            status=BrewSessionStatus.PAUSED,
            paused_at=timezone.now(),
            started_at=timezone.now(),
        )
        self.url = reverse("brew-session-cancel", args=[self.session.pk])

    def test_paused_session_can_be_cancelled_without_telemetry(self):
        response = self.client.post(self.url)
        self.assertRedirects(
            response, reverse("brew-session-detail", args=[self.session.pk])
        )
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, BrewSessionStatus.CANCELLED)
        self.assertIsNotNone(self.session.completed_at)
        self.assertFalse(self.session.temperature_override)
        self.assertEqual(self.session.current_step_index, 0)
        for name in ["brewery-list", "brew-session-list", "brew-session-detail"]:
            args = [self.session.pk] if name == "brew-session-detail" else []
            response = self.client.get(reverse(name, args=args))
            self.assertNotContains(response, 'action="' + self.url + '"')
        with self.assertRaises(SessionStateError):
            resume_session(self.session.pk)
        with self.assertRaises(SessionStartError):
            start_session(self.session.pk)

    def test_cancellable_states_preserve_progress_and_cancel_is_idempotent(self):
        for state in [BrewSessionStatus.PAUSED, BrewSessionStatus.PENDING]:
            with self.subTest(state=state):
                now = timezone.now()
                self.session.status = state
                self.session.started_at = None if state == BrewSessionStatus.PENDING else now
                self.session.step_elapsed_seconds = 12
                self.session.step_started_at = now - timedelta(seconds=20)
                self.session.paused_at = (
                    now - timedelta(seconds=5)
                    if state == BrewSessionStatus.PAUSED
                    else None
                )
                self.session.save()
                cancelled, progress = cancel_session(self.session.pk, now=now)
                expected = 27 if state == BrewSessionStatus.PAUSED else 32
                self.assertEqual(progress.step_elapsed_seconds, expected)
                again, later = cancel_session(
                    self.session.pk, now=now + timedelta(minutes=1)
                )
                self.assertEqual(again.completed_at, cancelled.completed_at)
                self.assertEqual(later.elapsed_seconds, progress.elapsed_seconds)

    def test_cancel_rejects_running_heating_or_finished_sessions(self):
        for state in [
            BrewSessionStatus.RUNNING,
            BrewSessionStatus.HEATING,
            BrewSessionStatus.WAITING,
            BrewSessionStatus.COMPLETED,
            BrewSessionStatus.FAILED,
        ]:
            self.session.status = state
            self.session.save()
            with self.assertRaises(SessionStateError):
                cancel_session(self.session.pk)
            self.session.refresh_from_db()
            self.assertEqual(self.session.status, state)

    def test_stale_refresh_cannot_revive_cancelled_session(self):
        stale = BrewSession.objects.get(pk=self.session.pk)
        stale.status = BrewSessionStatus.RUNNING
        stale.step_started_at = timezone.now() - timedelta(seconds=200)
        stale.temperature_override = True
        cancel_session(self.session.pk)
        refresh_session(stale)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, BrewSessionStatus.CANCELLED)
        self.assertEqual(stale.status, BrewSessionStatus.CANCELLED)

    def test_cancel_controls_are_visible_and_translated(self):
        with override("uk"):
            for name in ["brewery-list", "brew-session-list", "brew-session-detail"]:
                args = [self.session.pk] if name == "brew-session-detail" else []
                response = self.client.get(
                    reverse(name, args=args), HTTP_ACCEPT_LANGUAGE="uk"
                )
                self.assertContains(response, 'action="' + self.url + '"')
                self.assertContains(response, "Скасувати варіння")

    def test_post_csrf_and_missing_session(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(
            Client(enforce_csrf_checks=True).post(self.url).status_code, 403
        )
        self.assertEqual(
            self.client.post(reverse("brew-session-cancel", args=[999999])).status_code,
            404,
        )

    def test_running_session_requires_pause_before_cancellation(self):
        from apps.main.services.session_engine import pause_session
        self.session.status = BrewSessionStatus.RUNNING
        self.session.temperature_override = True
        self.session.save()
        self.client.post(self.url)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, BrewSessionStatus.RUNNING)
        response = self.client.get(reverse("brew-session-list"))
        self.assertNotContains(response, 'action="' + self.url + '"')
        pause_session(self.session.pk)
        self.client.post(self.url)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, BrewSessionStatus.CANCELLED)

    def test_cancel_button_hidden_while_waiting_for_temperature(self):
        self.session.status = BrewSessionStatus.WAITING
        self.session.save()
        for name in ["brewery-list", "brew-session-list", "brew-session-detail"]:
            args = [self.session.pk] if name == "brew-session-detail" else []
            response = self.client.get(reverse(name, args=args))
            self.assertNotContains(response, 'action="' + self.url + '"')
            self.assertNotContains(response, "Pause the session to cancel it")

    def test_unstarted_session_has_cancel_button(self):
        self.session.status = BrewSessionStatus.PENDING
        self.session.started_at = None
        self.session.paused_at = None
        self.session.save()
        for name in ["brewery-list", "brew-session-list", "brew-session-detail"]:
            args = [self.session.pk] if name == "brew-session-detail" else []
            self.assertContains(self.client.get(reverse(name, args=args)), 'action="' + self.url + '"')
        self.client.post(self.url)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, BrewSessionStatus.CANCELLED)

    def test_cancelled_session_can_be_deleted_from_list(self):
        cancel_session(self.session.pk)
        response = self.client.get(reverse("brew-session-list"))
        self.assertContains(response, 'action="' + reverse("brew-session-delete") + '"')
        response = self.client.post(reverse("brew-session-delete"), {"session_id": self.session.pk})
        self.assertRedirects(response, reverse("brew-session-list"))
        self.assertFalse(BrewSession.objects.filter(pk=self.session.pk).exists())
        self.assertTrue(Recipe.objects.filter(pk=self.recipe.pk).exists())

    def test_active_and_unstarted_sessions_cannot_be_deleted(self):
        for state in [BrewSessionStatus.PENDING, BrewSessionStatus.RUNNING,
                      BrewSessionStatus.HEATING, BrewSessionStatus.WAITING, BrewSessionStatus.PAUSED]:
            with self.subTest(state=state):
                self.session.status = state
                self.session.save()
                self.client.post(reverse("brew-session-delete"), {"session_id": self.session.pk})
                self.assertTrue(BrewSession.objects.filter(pk=self.session.pk).exists())
