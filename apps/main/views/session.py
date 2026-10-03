from django.views.decorators.http import require_POST
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils.translation import gettext as _
from django.utils import timezone
from django.utils.timezone import localtime
from apps.main.forms import BrewSessionForm
from apps.main.models.sensor import Sensor
from apps.main.models.recipe import RecipeStepMode
from apps.main.models.session import BrewSession, BrewSessionStatus
from apps.main.services.session_engine import DEMO_TELEMETRY_MAX_AGE_SECONDS, TEMPERATURE_TOLERANCE, demo_hardware_is_ready, refresh_session, cancel_session, SessionStateError, step_duration_seconds


def brew_session_list_view(request):

    sessions = list(
        BrewSession.objects.select_related(
            "brewery",
            "recipe",
        )
        .prefetch_related("recipe__steps")
        .order_by("-created_at")
    )
    for session in sessions:
        if session.status in [
            BrewSessionStatus.RUNNING,
            BrewSessionStatus.HEATING,
            BrewSessionStatus.WAITING,
        ]:
            refresh_session(session)

    return render(
        request,
        "main/brew_session_list.html",
        {
            "sessions": sessions,
        },
    )



def brew_session_create_view(request):

    if request.method == "POST":

        form = BrewSessionForm(request.POST)

        if form.is_valid():

            session = form.save()

            return redirect(
                "brew-session-detail",
                session.id,
            )

    else:
        form = BrewSessionForm()

    return render(
        request,
        "main/brew_session_form.html",
        {
            "form": form,
        },
    )



def brew_session_detail_view(
    request,
    session_id,
):

    session = get_object_or_404(
        BrewSession.objects.select_related(
            "recipe",
            "brewery",
        ),
        pk=session_id,
    )

    session_progress = refresh_session(session)

    steps = list(session.recipe.steps.all())

    current_step = None

    if (
        session.status != BrewSessionStatus.COMPLETED
        and session.current_step_index < len(steps)
    ):
        current_step = steps[session.current_step_index]

    temperature_chart = _session_temperature_chart(session)
    latest_temperature = None
    latest_temperature_at = None
    temperature_is_live = False
    temperature_out_of_range = False
    mash_sensor = Sensor.objects.filter(
        controller__brewery=session.brewery,
        key="mash_temperature_sensor",
    ).first()
    if mash_sensor:
        latest = mash_sensor.telemetry.first()
        latest_temperature = latest.value if latest else None
        latest_temperature_at = latest.created_at if latest else None
        temperature_is_live = bool(
            latest
            and (timezone.now() - latest.created_at).total_seconds()
            <= DEMO_TELEMETRY_MAX_AGE_SECONDS
        )
    if (
        current_step
        and session.status
        in [
            BrewSessionStatus.RUNNING,
            BrewSessionStatus.HEATING,
            BrewSessionStatus.WAITING,
            BrewSessionStatus.PAUSED,
        ]
        and latest_temperature is not None
        and current_step.mode == RecipeStepMode.HOLD_TEMPERATURE
    ):
        temperature_out_of_range = abs(
            latest_temperature - current_step.target_temperature
        ) > TEMPERATURE_TOLERANCE

    step_progresses = []
    for index, step in enumerate(steps):
        duration = step_duration_seconds(session, steps, index)
        is_completed = index < session.current_step_index
        is_current = (
            index == session.current_step_index
            and session.status
            in [
                BrewSessionStatus.RUNNING,
                BrewSessionStatus.HEATING,
                BrewSessionStatus.WAITING,
                BrewSessionStatus.PAUSED,
            ]
        )
        elapsed = duration if is_completed else 0
        if is_current:
            elapsed = session_progress.step_elapsed_seconds
        step_progresses.append(
            {
                "step": step,
                "is_completed": is_completed,
                "is_current": is_current,
                "duration_seconds": duration,
                "elapsed_seconds": elapsed,
                "elapsed_minutes": elapsed // 60,
                "elapsed_remainder": elapsed % 60,
                "duration_minutes": duration // 60,
                "duration_remainder": duration % 60,
                "percent": min(100, int(elapsed * 100 / duration)) if duration else 0,
            }
        )

    return render(
        request,
        "main/brew_session_detail.html",
        {
            "session": session,
            "steps": steps,
            "step_progresses": step_progresses,
            "current_step": current_step,
            "session_progress": session_progress,
            "demo_ready": demo_hardware_is_ready(session.brewery),
            "temperature_chart": temperature_chart,
            "latest_temperature": latest_temperature,
            "latest_temperature_at": latest_temperature_at,
            "temperature_is_live": temperature_is_live,
            "temperature_out_of_range": temperature_out_of_range,
        },
    )



def brew_session_delete_view(request):
    if request.method == "POST":
        session = get_object_or_404(BrewSession, pk=request.POST.get("session_id"))
        if session.status in (BrewSessionStatus.COMPLETED, BrewSessionStatus.CANCELLED):
            session.delete()
            messages.success(request, _("Brew session deleted."))
        else:
            messages.error(request, _("Only completed or cancelled brew sessions can be deleted."))
    return redirect("brew-session-list")



def _session_temperature_chart(session):
    if not session.started_at:
        return {"datasets": []}
    end = session.completed_at or timezone.now()
    sensors = Sensor.objects.filter(
        controller__brewery=session.brewery,
        kind="temperature",
        is_enabled=True,
    )
    colors = ["#ff6384", "#36a2eb", "#4bc0c0", "#ffcd56"]
    datasets = []
    for index, sensor in enumerate(sensors):
        points = list(
            sensor.telemetry.filter(
                created_at__gte=session.started_at,
                created_at__lte=end,
            ).order_by("created_at")[:1000]
        )
        if not points:
            continue
        latest = points[-1]
        datasets.append(
            {
                "label": sensor.name,
                "unit": sensor.unit,
                "latestValue": latest.value,
                "latestAt": localtime(latest.created_at).strftime("%H:%M:%S"),
                "isLive": (
                    session.completed_at is None
                    and (timezone.now() - latest.created_at).total_seconds()
                    <= DEMO_TELEMETRY_MAX_AGE_SECONDS
                ),
                "borderColor": colors[index % len(colors)],
                "backgroundColor": colors[index % len(colors)],
                "pointBackgroundColor": colors[index % len(colors)],
                "data": [
                    {
                        "x": localtime(point.created_at).strftime("%H:%M:%S"),
                        "y": point.value,
                    }
                    for point in points
                ],
            }
        )
    return {"datasets": datasets}



@require_POST
def brew_session_cancel_view(request, session_id):
    get_object_or_404(BrewSession, pk=session_id)
    try:
        cancel_session(session_id)
    except SessionStateError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, _("Brew session cancelled."))
    return redirect("brew-session-detail", session_id=session_id)
