from dataclasses import dataclass
from datetime import timedelta
from typing import Optional, Tuple

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _, gettext_noop

from apps.main.models.session import BrewSession, BrewSessionStatus


DEMO_STEP_SECONDS = 60
DEMO_CYCLE_SECONDS = 3 * DEMO_STEP_SECONDS
DEMO_STEPS = (
    gettext_noop("Mash in"),
    gettext_noop("Mash rest"),
    gettext_noop("Mash out"),
)


class SessionStartError(Exception):
    """Raised when a brew session cannot be started."""


@dataclass(frozen=True)
class SessionProgress:
    step_name: Optional[str]
    step_index: int
    elapsed_seconds: int
    remaining_seconds: int
    percent: int


def refresh_session(session: BrewSession, *, now=None) -> SessionProgress:
    """Bring a running demo session in sync with elapsed wall-clock time."""
    now = now or timezone.now()

    if session.status != BrewSessionStatus.RUNNING or not session.started_at:
        return _progress_for(session, now)

    elapsed = max(0, int((now - session.started_at).total_seconds()))
    new_step_index = min(elapsed // DEMO_STEP_SECONDS, len(DEMO_STEPS))
    update_fields = []

    if session.current_step_index != new_step_index:
        session.current_step_index = new_step_index
        update_fields.append("current_step_index")

    if elapsed >= DEMO_CYCLE_SECONDS:
        session.status = BrewSessionStatus.COMPLETED
        session.completed_at = session.started_at + timedelta(seconds=DEMO_CYCLE_SECONDS)
        session.current_step_index = len(DEMO_STEPS)
        update_fields.extend(["status", "completed_at"])

    if update_fields:
        session.save(update_fields=list(dict.fromkeys(update_fields)))

    return _progress_for(session, now)


@transaction.atomic
def start_session(session_id: int, *, now=None) -> Tuple[BrewSession, SessionProgress]:
    """Atomically start one pending session for a brewery."""
    now = now or timezone.now()
    session = BrewSession.objects.select_for_update().get(pk=session_id)

    if session.status != BrewSessionStatus.PENDING:
        raise SessionStartError(_("Only a pending brew session can be started."))

    running_session = (
        BrewSession.objects.select_for_update()
        .filter(brewery=session.brewery, status=BrewSessionStatus.RUNNING)
        .exclude(pk=session.pk)
        .first()
    )
    if running_session:
        refresh_session(running_session, now=now)
        if running_session.status == BrewSessionStatus.RUNNING:
            raise SessionStartError(_("This brewery already has a running brew session."))

    session.status = BrewSessionStatus.RUNNING
    session.started_at = now
    session.completed_at = None
    session.current_step_index = 0
    session.save(
        update_fields=["status", "started_at", "completed_at", "current_step_index"]
    )
    return session, _progress_for(session, now)


def _progress_for(session: BrewSession, now) -> SessionProgress:
    elapsed = 0
    if session.started_at:
        elapsed = max(0, int((now - session.started_at).total_seconds()))
    elapsed = min(elapsed, DEMO_CYCLE_SECONDS)
    remaining = max(0, DEMO_CYCLE_SECONDS - elapsed)
    step_index = min(session.current_step_index, len(DEMO_STEPS))
    step_name = DEMO_STEPS[step_index] if step_index < len(DEMO_STEPS) else None
    return SessionProgress(
        step_name=step_name,
        step_index=step_index,
        elapsed_seconds=elapsed,
        remaining_seconds=remaining,
        percent=min(100, int(elapsed * 100 / DEMO_CYCLE_SECONDS)),
    )
