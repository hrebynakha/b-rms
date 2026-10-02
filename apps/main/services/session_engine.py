from dataclasses import dataclass
from datetime import timedelta
from typing import Optional, Tuple

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.main.models.recipe import RecipeStepMode
from apps.main.models.session import BrewSession, BrewSessionMode, BrewSessionStatus
from apps.main.models.telemetry import Telemetry


DEMO_CYCLE_SECONDS = 180
DEMO_TELEMETRY_MAX_AGE_SECONDS = 10
DEMO_TEMPERATURE_SENSOR_KEY = "mash_temperature_sensor"
TEMPERATURE_TOLERANCE = 1.0


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
    step_mode: Optional[str]
    step_elapsed_seconds: int
    step_duration_seconds: int
    step_remaining_seconds: int
    step_remaining_minutes: int
    step_remaining_seconds_remainder: int
    elapsed_seconds: int
    remaining_seconds: int
    percent: int
    waiting_for_temperature: bool
    target_temperature: Optional[float]
    current_temperature: Optional[float]
    minimum_temperature: Optional[float]
    maximum_temperature: Optional[float]


def refresh_session(session: BrewSession, *, now=None) -> SessionProgress:
    """Advance a session only after its target temperature has been reached."""
    now = now or timezone.now()

    steps = list(session.recipe.steps.all())

    if (
        session.status
        not in [
            BrewSessionStatus.RUNNING,
            BrewSessionStatus.HEATING,
            BrewSessionStatus.WAITING,
            BrewSessionStatus.PAUSED,
        ]
        or not session.started_at
    ):
        return _progress_for(session, now, steps)

    if session.status == BrewSessionStatus.PAUSED:
        return _progress_for(session, now, steps)

    update_fields = []
    if session.current_step_index >= len(steps):
        session.status = BrewSessionStatus.COMPLETED
        session.completed_at = now
        update_fields.extend(["status", "completed_at"])
    else:
        step = steps[session.current_step_index]
        current_temperature = _current_temperature(session, now)
        in_range = _temperature_in_range(current_temperature, step)
        if step.mode == RecipeStepMode.REACH_TEMPERATURE:
            if session.temperature_override or in_range:
                session.current_step_index += 1
                session.step_started_at = None
                session.step_elapsed_seconds = 0
                session.temperature_override = False
                session.status = BrewSessionStatus.RUNNING
                update_fields.extend(
                    [
                        "current_step_index",
                        "step_started_at",
                        "step_elapsed_seconds",
                        "temperature_override",
                        "status",
                    ]
                )
                if session.current_step_index >= len(steps):
                    session.status = BrewSessionStatus.COMPLETED
                    session.completed_at = now
                    update_fields.extend(["status", "completed_at"])
            elif session.status != BrewSessionStatus.HEATING:
                session.status = BrewSessionStatus.HEATING
                update_fields.append("status")
        elif session.temperature_override or in_range:
            if session.status == BrewSessionStatus.WAITING:
                session.status = BrewSessionStatus.RUNNING
                update_fields.append("status")
            if session.step_started_at is None:
                session.step_started_at = now
                update_fields.append("step_started_at")
            step_elapsed = session.step_elapsed_seconds + max(
                0, int((now - session.step_started_at).total_seconds())
            )
            if step_elapsed >= step_duration_seconds(
                session, steps, session.current_step_index
            ):
                session.current_step_index += 1
                session.step_started_at = None
                session.step_elapsed_seconds = 0
                session.temperature_override = False
                session.status = BrewSessionStatus.WAITING
                update_fields.extend(
                    [
                        "current_step_index",
                        "step_started_at",
                        "step_elapsed_seconds",
                        "temperature_override",
                        "status",
                    ]
                )
                if session.current_step_index >= len(steps):
                    session.status = BrewSessionStatus.COMPLETED
                    session.completed_at = now
                    update_fields.extend(["status", "completed_at"])
        else:
            if session.step_started_at is not None:
                session.step_elapsed_seconds += max(
                    0, int((now - session.step_started_at).total_seconds())
                )
                session.step_started_at = None
                update_fields.extend(["step_elapsed_seconds", "step_started_at"])
            if session.status != BrewSessionStatus.WAITING:
                session.status = BrewSessionStatus.WAITING
                update_fields.append("status")

    if update_fields:
        # A concurrent page refresh must not revive a cancelled session.
        changed = BrewSession.objects.filter(pk=session.pk).exclude(
            status=BrewSessionStatus.CANCELLED,
        ).update(**{field: getattr(session, field) for field in set(update_fields)})
        if not changed:
            session.refresh_from_db()

    return _progress_for(session, now, steps)


@transaction.atomic
def start_session(session_id: int, *, now=None) -> Tuple[BrewSession, SessionProgress]:
    """Atomically start one pending session for a brewery."""
    now = now or timezone.now()
    session = BrewSession.objects.select_for_update().get(pk=session_id)

    from apps.main.models import ManualControl
    if ManualControl.objects.filter(Q(active=True) | Q(pump_on=True), controller__brewery=session.brewery).exists():
        raise SessionStartError(_("Stop manual temperature control first."))

    if session.status != BrewSessionStatus.PENDING:
        raise SessionStartError(_("Only a pending brew session can be started."))

    if not demo_hardware_is_ready(session.brewery, now=now):
        raise SessionStartError(
            _("No fresh telemetry from the temperature sensor.")
        )

    steps = list(session.recipe.steps.all())
    if not steps:
        raise SessionStartError(_("The selected recipe has no steps."))

    running_session = (
        BrewSession.objects.select_for_update()
        .filter(
            brewery=session.brewery,
            status__in=[
                BrewSessionStatus.RUNNING,
                BrewSessionStatus.HEATING,
                BrewSessionStatus.WAITING,
                BrewSessionStatus.PAUSED,
            ],
        )
        .exclude(pk=session.pk)
        .first()
    )
    if running_session:
        refresh_session(running_session, now=now)
        if running_session.status in [
            BrewSessionStatus.RUNNING,
            BrewSessionStatus.HEATING,
            BrewSessionStatus.WAITING,
            BrewSessionStatus.PAUSED,
        ]:
            raise SessionStartError(_("This brewery already has a running brew session."))

    session.status = BrewSessionStatus.RUNNING
    session.started_at = now
    session.completed_at = None
    session.paused_at = None
    session.paused_seconds = 0
    session.step_started_at = None
    session.step_elapsed_seconds = 0
    session.temperature_override = False
    session.current_step_index = 0
    session.save(
        update_fields=[
            "status",
            "started_at",
            "completed_at",
            "paused_at",
            "paused_seconds",
            "step_started_at",
            "step_elapsed_seconds",
            "temperature_override",
            "current_step_index",
        ]
    )
    return session, refresh_session(session, now=now)


@transaction.atomic
def pause_session(session_id: int, *, now=None):
    now = now or timezone.now()
    session = BrewSession.objects.select_for_update().get(pk=session_id)
    if session.status not in [
        BrewSessionStatus.RUNNING,
        BrewSessionStatus.HEATING,
        BrewSessionStatus.WAITING,
    ]:
        raise SessionStateError(_("Only a running session can be paused."))
    refresh_session(session, now=now)
    if session.status not in [
        BrewSessionStatus.RUNNING,
        BrewSessionStatus.HEATING,
        BrewSessionStatus.WAITING,
    ]:
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
            _("No fresh telemetry from the temperature sensor.")
        )
    paused_for = max(0, int((now - session.paused_at).total_seconds()))
    session.paused_seconds += paused_for
    if session.step_started_at:
        session.step_started_at += timedelta(seconds=paused_for)
    session.status = BrewSessionStatus.RUNNING
    session.paused_at = None
    session.save(
        update_fields=["status", "paused_at", "paused_seconds", "step_started_at"]
    )
    return session, refresh_session(session, now=now)


@transaction.atomic
def override_temperature(session_id: int, *, now=None):
    now = now or timezone.now()
    session = BrewSession.objects.select_for_update().get(pk=session_id)
    if session.status not in [BrewSessionStatus.HEATING, BrewSessionStatus.WAITING]:
        raise SessionStateError(_("The session is not waiting for temperature."))
    session.temperature_override = True
    session.save(update_fields=["temperature_override"])
    return session, refresh_session(session, now=now)


def _progress_for(session: BrewSession, now, steps=None) -> SessionProgress:
    steps = steps if steps is not None else list(session.recipe.steps.all())
    step_index = min(session.current_step_index, len(steps))
    step_name = steps[step_index].name if step_index < len(steps) else None
    step_mode = steps[step_index].mode if step_index < len(steps) else None
    step_number = step_index + 1 if step_name is not None else None
    durations = [step_duration_seconds(session, steps, index) for index in range(len(steps))]
    total_duration = sum(durations)
    completed_duration = sum(durations[:step_index])
    step_elapsed = session.step_elapsed_seconds
    if step_index < len(steps) and session.step_started_at:
        effective_now = (
            session.paused_at
            if session.status == BrewSessionStatus.PAUSED and session.paused_at
            else session.completed_at or now
        )
        step_elapsed = min(
            durations[step_index],
            step_elapsed
            + max(0, int((effective_now - session.step_started_at).total_seconds())),
        )
    elapsed = completed_duration + step_elapsed
    remaining = max(0, total_duration - elapsed)
    current_temperature = _current_temperature(session, now)
    target_temperature = (
        float(steps[step_index].target_temperature) if step_index < len(steps) else None
    )
    waiting = (
        session.status == BrewSessionStatus.WAITING
        and step_index < len(steps)
        and session.step_started_at is None
    )
    step_remaining = (
        max(0, durations[step_index] - step_elapsed) if step_index < len(steps) else 0
    )
    return SessionProgress(
        step_name=step_name,
        step_index=step_index,
        step_number=step_number,
        total_steps=len(steps),
        step_mode=step_mode,
        step_elapsed_seconds=step_elapsed,
        step_duration_seconds=durations[step_index] if step_index < len(steps) else 0,
        step_remaining_seconds=step_remaining,
        step_remaining_minutes=step_remaining // 60,
        step_remaining_seconds_remainder=step_remaining % 60,
        elapsed_seconds=elapsed,
        remaining_seconds=remaining,
        percent=min(100, int(elapsed * 100 / total_duration)) if total_duration else 0,
        waiting_for_temperature=waiting,
        target_temperature=target_temperature,
        current_temperature=current_temperature,
        minimum_temperature=(
            target_temperature - TEMPERATURE_TOLERANCE
            if target_temperature is not None
            else None
        ),
        maximum_temperature=(
            target_temperature + TEMPERATURE_TOLERANCE
            if target_temperature is not None
            else None
        ),
    )


def step_duration_seconds(session, steps, step_index):
    if steps[step_index].mode == RecipeStepMode.REACH_TEMPERATURE:
        return 0
    if session.mode == BrewSessionMode.STANDARD:
        return max(1, int(steps[step_index].duration_minutes * 60))
    total_weight = sum(
        step.duration_minutes
        for step in steps
        if step.mode == RecipeStepMode.HOLD_TEMPERATURE
    )
    if total_weight <= 0:
        return 1
    start = sum(
        step.duration_minutes
        for step in steps[:step_index]
        if step.mode == RecipeStepMode.HOLD_TEMPERATURE
    )
    end = start + steps[step_index].duration_minutes
    start_second = round(start * DEMO_CYCLE_SECONDS / total_weight)
    end_second = round(end * DEMO_CYCLE_SECONDS / total_weight)
    return max(1, end_second - start_second)


def _current_temperature(session, now):
    latest = (
        Telemetry.objects.filter(
            sensor__controller__brewery=session.brewery,
            sensor__key=DEMO_TEMPERATURE_SENSOR_KEY,
            sensor__is_enabled=True,
            sensor__controller__is_enabled=True,
        )
        .order_by("-created_at", "-pk")
        .first()
    )
    if not latest:
        return None
    if (now - latest.created_at).total_seconds() > DEMO_TELEMETRY_MAX_AGE_SECONDS:
        return None
    return latest.value


def _temperature_in_range(current_temperature, step):
    if current_temperature is None:
        return False
    target = float(step.target_temperature)
    return target - TEMPERATURE_TOLERANCE <= current_temperature <= target + TEMPERATURE_TOLERANCE


@transaction.atomic
def cancel_session(session_id: int, *, now=None):
    now = now or timezone.now()
    session = BrewSession.objects.select_for_update().get(pk=session_id)
    if session.status == BrewSessionStatus.CANCELLED:
        return session, _progress_for(session, now)
    if session.status != BrewSessionStatus.PAUSED and not (
        session.status == BrewSessionStatus.PENDING and session.started_at is None
    ):
        raise SessionStateError(_("Only a paused or unstarted brew session can be cancelled."))
    progress = _progress_for(session, now)
    session.step_elapsed_seconds = progress.step_elapsed_seconds
    session.step_started_at = None
    session.paused_at = None
    session.temperature_override = False
    session.status = BrewSessionStatus.CANCELLED
    session.completed_at = now
    session.save(update_fields=["step_elapsed_seconds", "step_started_at", "paused_at",
                                "temperature_override", "status", "completed_at"])
    return session, _progress_for(session, now)
