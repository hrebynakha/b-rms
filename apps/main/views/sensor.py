from datetime import timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q
from django.utils.translation import gettext as _
from django.utils import timezone
from django.utils.timezone import localtime
from apps.main.forms import TelemetryCleanupForm
from apps.main.models.sensor import Sensor
from apps.main.models.telemetry import Telemetry
from apps.main.models.session import BrewSession
from apps.main.services.session_engine import DEMO_TELEMETRY_MAX_AGE_SECONDS


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
