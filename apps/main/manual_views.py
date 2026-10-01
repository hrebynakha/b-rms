import math

from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.main.models import Controller, ManualControl
from apps.main.manual_messages import manual_messages
from apps.main.models.session import BrewSession, BrewSessionStatus
from apps.main.services.manual_control import control_state, record_sample, update_from_telemetry


class ManualSettingsSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["start", "apply", "stop"])
    target_temperature = serializers.FloatField(min_value=30, max_value=100, required=False)
    warning_delta = serializers.FloatField(min_value=1, max_value=50, required=False)
    warning_mode = serializers.ChoiceField(choices=["degrees", "percent"], required=False)

    def validate(self, attrs):
        if any(not math.isfinite(attrs[key]) for key in ("target_temperature", "warning_delta") if key in attrs):
            raise serializers.ValidationError(_("Values must be finite numbers."))
        if any(attrs[key] % 1 for key in ("target_temperature", "warning_delta") if key in attrs):
            raise serializers.ValidationError(_("Target temperature and warning threshold must be whole numbers."))
        return attrs


@require_GET
def manual_control_view(request, controller_id):
    controller = get_object_or_404(Controller, pk=controller_id)
    control, _ = ManualControl.objects.get_or_create(controller=controller)
    return render(request, "main/manual_control.html", {
        "controller": controller, "control": control, "manual_messages": manual_messages(),
    })


@require_GET
def manual_status_view(request, controller_id):
    controller = get_object_or_404(Controller, pk=controller_id)
    control, _ = ManualControl.objects.get_or_create(controller=controller)
    update_from_telemetry_if_unsafe(control)
    state = control_state(control)
    chart_since = timezone.now() if request.GET.get("reset_chart") == "1" else None
    samples = control.samples.order_by("-pk")
    if chart_since:
        samples = samples.filter(created_at__gte=chart_since)
        state["chart_since"] = chart_since.isoformat()
    state["history"] = [
        {"at": sample.created_at.isoformat(), "temperature": sample.temperature,
         "target": sample.target_temperature, "voltage": sample.signal_voltage,
         "measured_voltage": sample.measured_voltage}
        for sample in reversed(list(samples[:200]))
    ]
    response = JsonResponse(state)
    response["Cache-Control"] = "no-store"
    return response


def update_from_telemetry_if_unsafe(control):
    if control.active and control_state(control)["status"] in ("no_data", "overheat"):
        update_from_telemetry(control.controller)
        control.refresh_from_db()


@require_POST
@transaction.atomic
def manual_action_view(request, controller_id):
    controller = get_object_or_404(Controller, pk=controller_id)
    ManualControl.objects.get_or_create(controller=controller)
    control = ManualControl.objects.select_for_update().get(controller=controller)
    payload = {"action": "stop"} if request.POST.get("action") == "stop" else request.POST
    serializer = ManualSettingsSerializer(data=payload)
    if not serializer.is_valid():
        return JsonResponse({"errors": serializer.errors}, status=400)
    data = serializer.validated_data
    action = data.pop("action")
    if action != "stop":
        for key, value in data.items():
            setattr(control, key, value)
        state = control_state(control)
        if action == "start" or control.active:
            if not state["live"] or not controller.is_enabled or controller.wifi_reset_command:
                return JsonResponse({"detail": _("Fresh sensor readings and an available controller are required.")}, status=409)
            if state["overheat"]:
                return JsonResponse({"detail": _("The temperature exceeds the overheat threshold. Wait for cooling.")}, status=409)
            if BrewSession.objects.filter(brewery=controller.brewery, status__in=[
                BrewSessionStatus.RUNNING, BrewSessionStatus.HEATING,
                BrewSessionStatus.WAITING, BrewSessionStatus.PAUSED,
            ]).exists():
                return JsonResponse({"detail": _("Finish the active brew session first.")}, status=409)
        if action == "start":
            control.active = True
    else:
        control.active = False
    control.revision += 1
    control.save()
    chart_since = timezone.now()
    record_sample(control)
    state = control_state(control)
    if action in ("start", "apply"):
        state["chart_since"] = chart_since.isoformat()
    return JsonResponse(state)
