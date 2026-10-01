from datetime import timedelta
from types import SimpleNamespace

from django.test import SimpleTestCase
from django.utils import timezone

from apps.main.services.heating_estimate import heating_estimate


class HeatingEstimateTests(SimpleTestCase):
    def series(self, values, gap=3):
        now = timezone.now()
        return [SimpleNamespace(value=value, created_at=now - timedelta(seconds=index * gap))
                for index, value in enumerate(reversed(values))]

    def estimate(self, values, **kwargs):
        return heating_estimate(self.series(values), 30, active=True, available=True, **kwargs)

    def test_requires_five_intervals_and_predicts_from_timestamps(self):
        self.assertEqual(self.estimate([20, 21, 22, 23, 24])["eta_status"], "collecting")
        state = self.estimate([20, 21, 22, 23, 24, 25])
        self.assertEqual(state["estimate_intervals"], 5)
        self.assertEqual(state["heating_rate_c_per_min"], 20)
        self.assertEqual(state["eta_seconds"], 15)

    def test_no_prediction_for_cooling_stable_or_inactive_readings(self):
        for values in [[25] * 6, [26, 25, 24, 23, 22, 21]]:
            state = self.estimate(values)
            self.assertIsNone(state["eta_seconds"])
            self.assertEqual(state["eta_status"], "not_warming")
        for active, available in [(False, True), (True, False)]:
            state = heating_estimate(self.series([20, 21, 22, 23, 24, 25]), 30, active=active, available=available)
            self.assertIsNone(state["eta_seconds"])

    def test_ignores_old_settings_and_gaps(self):
        readings = self.series([20, 21, 22, 23, 24, 25])
        state = heating_estimate(readings, 30, active=True, available=True, since=readings[2].created_at)
        self.assertEqual(state["eta_status"], "collecting")
        state = heating_estimate(self.series([20, 21, 22, 23, 24, 25], gap=15), 30, active=True, available=True)
        self.assertEqual(state["estimate_intervals"], 0)

    def test_target_reached_has_zero_remaining_time(self):
        self.assertEqual(self.estimate([30])["eta_seconds"], 0)
