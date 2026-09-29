from dataclasses import dataclass
from datetime import timedelta
from typing import Optional, Tuple

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.main.models.session import BrewSession, BrewSessionStatus
from apps.main.models.telemetry import Telemetry


DEMO_CYCLE_SECONDS = 180
DEMO_TELEMETRY_MAX_AGE_SECONDS = 10
DEMO_TEMPERATURE_SENSOR_KEY = "mash_temperature_sensor"


class SessionStartError(Exception):
    """Raised when a brew session cannot be started."""


class SessionStateError(Exception):
    """Raised when pausing or resuming is not valid."""


def demo_hardware_is_ready(brewery, *, now=None) -> bool:
    """Return whether the demo temperature feed reported recently."""
    now = now or timezone.now()
    cutoff = now - timedelta(seconds=DEMO_TELEMETRY_MAX_AGE_SECONDS)
    return Telemetry.objects.filter(
        sensor__controller__brewery=brewery,
        sensor__controller__is_enabled=True,
        sensor__is_enabled=True,
        sensor__key=DEMO_TEMPERATURE_SENSOR_KEY,
        created_at__gte=cutoff,
    ).exists()


@dataclass(frozen=True)
class SessionProgress:
    step_name: Optional[str]
    step_index: int
    step_number: Optional[int]
    total_steps: int
    step_remaining_seconds: int
    step_remaining_minutes: int
    step_remaining_seconds_remainder: int
    elapsed_seconds: int
    remaining_seconds: int
    percent: int


def refresh_session(session: BrewSession, *, now=None) -> SessionProgress:
    """Bring a running demo session in sync with elapsed wall-clock time."""
    now = now or timezone.now()

    steps = list(session.recipe.steps.all())

    if session.status not in [BrewSessionStatus.RUNNING, BrewSessionStatus.PAUSED] or not session.started_at:
        return _progress_for(session, now, steps)

    elapsed = _elapsed_seconds(session, now)
    new_step_index = _step_index_for_elapsed(elapsed, steps)
    update_fields = []

    if session.current_step_index != new_step_index:
        session.current_step_index = new_step_index
        update_fields.append("current_step_index")

    if elapsed >= DEMO_CYCLE_SECONDS:
        session.status = BrewSessionStatus.COMPLETED
        session.completed_at = now
        session.current_step_index = len(steps)
        update_fields.extend(["status", "completed_at"])

    if update_fields:
        session.save(update_fields=list(dict.fromkeys(update_fields)))

    return _progress_for(session, now, steps)


@transaction.atomic
def start_session(session_id: int, *, now=None) -> Tuple[BrewSession, SessionProgress]:
    """Atomically start one pending session for a brewery."""
    now = now or timezone.now()
    session = BrewSession.objects.select_for_update().get(pk=session_id)

    if session.status != BrewSessionStatus.PENDING:
        raise SessionStartError(_("Only a pending brew session can be started."))

    if not demo_hardware_is_ready(session.brewery, now=now):
        raise SessionStartError(
            _("Demo scripts are inactive. Start the ESP32 and telemetry scripts.")
        )

    steps = list(session.recipe.steps.all())
    if not steps or sum(step.duration_minutes for step in steps) <= 0:
        raise SessionStartError(_("The selected recipe has no steps with a duration."))

    running_session = (
        BrewSession.objects.select_for_update()
        .filter(
            brewery=session.brewery,
            status__in=[BrewSessionStatus.RUNNING, BrewSessionStatus.PAUSED],
        )
        .exclude(pk=session.pk)
        .first()
    )
    if running_session:
        refresh_session(running_session, now=now)
        if running_session.status in [BrewSessionStatus.RUNNING, BrewSessionStatus.PAUSED]:
            raise SessionStartError(_("This brewery already has a running brew session."))

    session.status = BrewSessionStatus.RUNNING
    session.started_at = now
    session.completed_at = None
    session.paused_at = None
    session.paused_seconds = 0
    session.current_step_index = 0
    session.save(
        update_fields=[
            "status",
            "started_at",
            "completed_at",
            "paused_at",
            "paused_seconds",
            "current_step_index",
        ]
    )
    return session, _progress_for(session, now, steps)


@transaction.atomic
def pause_session(session_id: int, *, now=None):
    now = now or timezone.now()
    session = BrewSession.objects.select_for_update().get(pk=session_id)
    if session.status != BrewSessionStatus.RUNNING:
        raise SessionStateError(_("Only a running session can be paused."))
    refresh_session(session, now=now)
    if session.status != BrewSessionStatus.RUNNING:
        raise SessionStateError(_("The session has already completed."))
    session.status = BrewSessionStatus.PAUSED
    session.paused_at = now
    session.save(update_fields=["status", "paused_at"])
    return session, _progress_for(session, now)


@transaction.atomic
def resume_session(session_id: int, *, now=None):
    now = now or timezone.now()
    session = BrewSession.objects.select_for_update().get(pk=session_id)
    if session.status != BrewSessionStatus.PAUSED or not session.paused_at:
        raise SessionStateError(_("Only a paused session can be resumed."))
    if not demo_hardware_is_ready(session.brewery, now=now):
        raise SessionStateError(
            _("Demo scripts are inactive. Start the ESP32 and telemetry scripts.")
        )
    session.paused_seconds += max(0, int((now - session.paused_at).total_seconds()))
    session.status = BrewSessionStatus.RUNNING
    session.paused_at = None
    session.save(update_fields=["status", "paused_at", "paused_seconds"])
    return session, _progress_for(session, now)


def _step_index_for_elapsed(elapsed_seconds: int, steps) -> int:
    """Map demo time to a recipe step, weighted by each step's duration."""
    if elapsed_seconds >= DEMO_CYCLE_SECONDS:
        return len(steps)

    total_duration = sum(step.duration_minutes for step in steps)
    if total_duration <= 0:
        return len(steps)

    elapsed_weight = max(0, elapsed_seconds) * total_duration
    cumulative_duration = 0
    for index, step in enumerate(steps):
        cumulative_duration += step.duration_minutes
        if elapsed_weight < cumulative_duration * DEMO_CYCLE_SECONDS:
            return index

    return len(steps)


def _progress_for(session: BrewSession, now, steps=None) -> SessionProgress:
    steps = steps if steps is not None else list(session.recipe.steps.all())
    elapsed = 0
    if session.started_at:
        elapsed = _elapsed_seconds(session, now)
    elapsed = min(elapsed, DEMO_CYCLE_SECONDS)
    remaining = max(0, DEMO_CYCLE_SECONDS - elapsed)
    step_index = min(session.current_step_index, len(steps))
    step_name = steps[step_index].name if step_index < len(steps) else None
    step_number = step_index + 1 if step_name is not None else None
    step_remaining = _step_remaining_seconds(elapsed, step_index, steps)
    return SessionProgress(
        step_name=step_name,
        step_index=step_index,
        step_number=step_number,
        total_steps=len(steps),
        step_remaining_seconds=step_remaining,
        step_remaining_minutes=step_remaining // 60,
        step_remaining_seconds_remainder=step_remaining % 60,
        elapsed_seconds=elapsed,
        remaining_seconds=remaining,
        percent=min(100, int(elapsed * 100 / DEMO_CYCLE_SECONDS)),
    )


def _elapsed_seconds(session: BrewSession, now) -> int:
    effective_now = session.paused_at if session.status == BrewSessionStatus.PAUSED else now
    return max(
        0,
        int((effective_now - session.started_at).total_seconds())
        - session.paused_seconds,
    )


def _step_remaining_seconds(elapsed_seconds: int, step_index: int, steps) -> int:
    if step_index >= len(steps):
        return 0

    total_duration = sum(step.duration_minutes for step in steps)
    if total_duration <= 0:
        return 0

    cumulative_duration = sum(
        step.duration_minutes for step in steps[: step_index + 1]
    )
    # Round the proportional boundary up so every fractional demo second stays
    # assigned to the current recipe step.
    step_end_second = (
        cumulative_duration * DEMO_CYCLE_SECONDS + total_duration - 1
    ) // total_duration
    return max(0, step_end_second - elapsed_seconds)
