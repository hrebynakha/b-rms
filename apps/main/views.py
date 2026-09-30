from datetime import timedelta

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Prefetch, Q
from django.utils.translation import gettext as _
from django.utils import timezone
from django.utils.timezone import localtime

from apps.main.forms import (
    BrewSessionForm,
    RecipeForm,
    BreweryDeleteForm,
    RecipeDeleteForm,
    TelemetryCleanupForm,
)
from apps.main.models.brewery import Brewery
from apps.main.models.sensor import Sensor
from apps.main.models.telemetry import Telemetry
from apps.main.models.recipe import Recipe, RecipeStep
from apps.main.models.recipe import RecipeStepMode
from apps.main.models.session import BrewSession, BrewSessionStatus
from apps.main.services.session_engine import (
    DEMO_TELEMETRY_MAX_AGE_SECONDS,
    TEMPERATURE_TOLERANCE,
    demo_hardware_is_ready,
    refresh_session,
    step_duration_seconds,
)


def index(request):
    return render(request, "main/index.html")


def brewery_list_view(request):

    active_sessions = BrewSession.objects.filter(
        status__in=[
            BrewSessionStatus.PENDING,
            BrewSessionStatus.RUNNING,
            BrewSessionStatus.HEATING,
            BrewSessionStatus.WAITING,
            BrewSessionStatus.PAUSED,
        ]
    ).select_related("recipe").order_by("-created_at")

    breweries = (
        Brewery.objects.prefetch_related(
            "controllers",
            "controllers__sensors",
            "controllers__sensors__telemetry",
            Prefetch(
                "brew_sessions",
                queryset=active_sessions,
                to_attr="active_brew_sessions",
            ),
        )
        .all()
        .order_by("-created_at")
    )

    for brewery in breweries:
        brewery.active_session = None
        brewery.session_progress = None
        pending_candidate = None
        for candidate in brewery.active_brew_sessions:
            progress = refresh_session(candidate)
            if candidate.status in [
                BrewSessionStatus.RUNNING,
                BrewSessionStatus.HEATING,
                BrewSessionStatus.WAITING,
                BrewSessionStatus.PAUSED,
            ]:
                brewery.active_session = candidate
                brewery.session_progress = progress
                break
            if candidate.status == BrewSessionStatus.PENDING and pending_candidate is None:
                pending_candidate = (candidate, progress)
        if brewery.active_session is None and pending_candidate:
            brewery.active_session, brewery.session_progress = pending_candidate
        brewery.demo_ready = demo_hardware_is_ready(brewery)

    has_active_session = any(
        brewery.active_session
        and brewery.active_session.status
        in [
            BrewSessionStatus.PENDING,
            BrewSessionStatus.RUNNING,
            BrewSessionStatus.HEATING,
            BrewSessionStatus.WAITING,
            BrewSessionStatus.PAUSED,
        ]
        for brewery in breweries
    )

    return render(
        request,
        "main/brewery_list.html",
        {
            "breweries": breweries,
            "has_active_session": has_active_session,
        },
    )


def sensor_detail_view(request, sensor_id):

    sensor = get_object_or_404(
        Sensor.objects.prefetch_related("telemetry"),
        id=sensor_id,
    )

    last_objects = sensor.telemetry.order_by("-created_at")[:50]

    # reverse for chart order
    data = list(reversed(last_objects))
    chart_data = {
        "labels": [localtime(item.created_at).strftime("%H:%M:%S") for item in data],
        "values": [item.value for item in data],
    }
    latest_telemetry = data[-1] if data else None
    telemetry_is_live = bool(
        latest_telemetry
        and (timezone.now() - latest_telemetry.created_at).total_seconds()
        <= DEMO_TELEMETRY_MAX_AGE_SECONDS
    )

    return render(
        request,
        "main/sensor_detail.html",
        {
            "sensor": sensor,
            "telemetry": data,
            "chart_data": chart_data,
            "cleanup_form": TelemetryCleanupForm(),
            "latest_telemetry": latest_telemetry,
            "telemetry_is_live": telemetry_is_live,
        },
    )


def recipe_list_view(request):
    search = request.GET.get("search", "")

    recipes = Recipe.objects.all()

    if search:
        recipes = recipes.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )

    return render(
        request,
        "main/recipe_list.html",
        {
            "recipes": recipes,
            "search": search,
        },
    )


def recipe_create_view(request):

    if request.method == "POST":

        form = RecipeForm(request.POST)

        if form.is_valid():

            recipe = form.save()

            names = request.POST.getlist("step_name")
            temperatures = request.POST.getlist("step_temperature")
            durations = request.POST.getlist("step_duration")
            modes = request.POST.getlist("step_mode")

            for step_index, name in enumerate(names):

                if not name:
                    continue

                RecipeStep.objects.create(
                    recipe=recipe,
                    order=step_index + 1,
                    name=name,
                    target_temperature=float(temperatures[step_index]),
                    duration_minutes=int(durations[step_index]),
                    mode=modes[step_index] if step_index < len(modes) else RecipeStepMode.HOLD_TEMPERATURE,
                )

            messages.success(request, _("Recipe created successfully."))

            return redirect("recipe-list")

    else:
        form = RecipeForm()

    return render(
        request,
        "main/recipe_form.html",
        {
            "form": form,
        },
    )


def recipe_edit_view(request, recipe_id=None):

    recipe = None
    steps = []

    if recipe_id:
        recipe = get_object_or_404(Recipe, pk=recipe_id)
        steps = list(
            recipe.steps.all().values(
                "id",
                "name",
                "target_temperature",
                "duration_minutes",
                "mode",
                "order",
            )
        )

    if request.method == "POST":

        if recipe:
            form = RecipeForm(request.POST, instance=recipe)
        else:
            form = RecipeForm(request.POST)

        if form.is_valid():

            recipe = form.save()

            # clear old steps (simple MVP approach)
            recipe.steps.all().delete()

            names = request.POST.getlist("step_name")
            temps = request.POST.getlist("step_temperature")
            durations = request.POST.getlist("step_duration")
            modes = request.POST.getlist("step_mode")

            for i, name in enumerate(names):

                if not name:
                    continue

                RecipeStep.objects.create(
                    recipe=recipe,
                    order=i + 1,
                    name=name,
                    target_temperature=float(temps[i]),
                    duration_minutes=int(durations[i]),
                    mode=modes[i] if i < len(modes) else RecipeStepMode.HOLD_TEMPERATURE,
                )

            return redirect("recipe-list")

    else:

        form = RecipeForm(instance=recipe)

    return render(
        request,
        "main/recipe_form.html",
        {
            "form": form,
            "recipe": recipe,
            "is_edit": recipe is not None,
            "steps": steps,
        },
    )


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


def brewery_delete_view(request):

    if request.method == "POST":

        form = BreweryDeleteForm(request.POST)

        if form.is_valid():

            brewery = get_object_or_404(
                Brewery,
                id=form.cleaned_data["brewery_id"],
            )

            brewery.delete()

            messages.success(
                request,
                "Brewery deleted successfully.",
            )

    return redirect("brewery-list")


def recipe_delete_view(request):

    if request.method == "POST":

        form = RecipeDeleteForm(request.POST)

        if form.is_valid():

            recipe = get_object_or_404(
                Recipe,
                id=form.cleaned_data["recipe_id"],
            )

            recipe.delete()

            messages.success(
                request,
                "Recipe deleted successfully.",
            )

    return redirect("recipe-list")


def brew_session_delete_view(request):
    if request.method == "POST":
        session = get_object_or_404(BrewSession, pk=request.POST.get("session_id"))
        if session.status == BrewSessionStatus.COMPLETED:
            session.delete()
            messages.success(request, _("Completed brew session deleted."))
        else:
            messages.error(request, _("Only completed brew sessions can be deleted."))
    return redirect("brew-session-list")


def sensor_cleanup_view(request, sensor_id):
    sensor = get_object_or_404(Sensor, pk=sensor_id)
    if request.method != "POST":
        return redirect("sensor-detail", sensor_id=sensor.id)
    form = TelemetryCleanupForm(request.POST)
    if not form.is_valid():
        messages.error(request, _("Invalid telemetry cleanup parameters."))
        return redirect("sensor-detail", sensor_id=sensor.id)

    telemetry = Telemetry.objects.filter(sensor=sensor)
    amount = form.cleaned_data["amount"]
    if form.cleaned_data["strategy"] == "minutes":
        cutoff = timezone.now() - timedelta(minutes=amount)
        deleted, deletion_details = telemetry.filter(created_at__lt=cutoff).delete()
    else:
        sessions = list(
            BrewSession.objects.filter(
                brewery=sensor.controller.brewery,
                started_at__isnull=False,
            ).order_by("-started_at")[:amount]
        )
        if not sessions:
            messages.error(request, _("There are no brew sessions to preserve."))
            return redirect("sensor-detail", sensor_id=sensor.id)
        keep = Q()
        now = timezone.now()
        for session in sessions:
            keep |= Q(
                created_at__gte=session.started_at,
                created_at__lte=session.completed_at or now,
            )
        deleted, deletion_details = telemetry.exclude(keep).delete()

    messages.success(
        request,
        _("Deleted %(count)s telemetry records.") % {"count": deleted},
    )
    return redirect("sensor-detail", sensor_id=sensor.id)


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
