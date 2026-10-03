from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Prefetch
from django.utils.translation import gettext as _
from django.utils import timezone
from apps.main.forms import BreweryDeleteForm
from apps.main.models.brewery import Brewery
from apps.main.models import Controller
from apps.main.services.manual_control import MAX_AGE_SECONDS
from apps.main.models.session import BrewSession, BrewSessionStatus
from apps.main.services.session_engine import demo_hardware_is_ready, refresh_session


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
            Prefetch("controllers", queryset=Controller.objects.select_related("manual_control")),
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
        now = timezone.now()
        for controller in brewery.controllers.all():
            control = getattr(controller, "manual_control", None)
            fresh = bool(control and control.reported_at
                         and control.reported_output_mode in ("direct", "time_pwm")
                         and 0 <= (now - control.reported_at).total_seconds() <= MAX_AGE_SECONDS)
            controller.output_statuses = [
                {"label": _("Heater · SSR"), "on": control.reported_ssr_on if fresh else None},
                {"label": _("Pump · circulation"), "on": control.reported_pump_on if fresh else None},
            ]


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
                _("Brewery deleted successfully."),
            )

    return redirect("brewery-list")
