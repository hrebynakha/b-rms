from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.api.serializers import ManualSettingsSerializer
from apps.main.models import Controller, ManualControl
from apps.main.services.manual_control import control_state
from apps.main.services.control_actions import (
    ControlActionError, apply_direct_action, apply_manual_action,
    update_from_telemetry_if_unsafe,
)


def action_response(action, *args):
    try:
        return JsonResponse(action(*args))
    except Controller.DoesNotExist as exc:
        raise Http404 from exc
    except ControlActionError as exc:
        return JsonResponse({"detail": str(exc)}, status=exc.status)


@require_GET
def direct_status_view(request, controller_id):
    controller = get_object_or_404(Controller, pk=controller_id)
    control, created = ManualControl.objects.get_or_create(controller=controller)
    update_from_telemetry_if_unsafe(control)
    response = JsonResponse(control_state(control))
    response['Cache-Control'] = 'no-store'
    return response



@require_GET
def manual_status_view(request, controller_id):
    controller = get_object_or_404(Controller, pk=controller_id)
    control, _ = ManualControl.objects.get_or_create(controller=controller)
    update_from_telemetry_if_unsafe(control)
    state = control_state(control)
    chart_since = timezone.now() if request.GET.get("reset_chart") == "1" else None
    samples = control.samples.order_by("-pk")
    if chart_since:
        samples = samples.filter(created_at__gt=chart_since)
        state["chart_since"] = chart_since.isoformat()
    state["history"] = [
        {"at": sample.created_at.isoformat(), "temperature": sample.temperature,
         "target": sample.target_temperature, "voltage": sample.signal_voltage,
         "power_percent": sample.power_percent if sample.output_mode == "time_pwm" else None,
         "ssr_on": sample.ssr_on,
         "measured_voltage": sample.measured_voltage}
        for sample in reversed(list(samples[:200]))
    ]
    response = JsonResponse(state)
    response["Cache-Control"] = "no-store"
    return response



@require_POST
def direct_action_view(request, controller_id):
    return action_response(apply_direct_action, controller_id, request.POST.get("output"), request.POST.get("on"))


@require_POST
def manual_action_view(request, controller_id):
    get_object_or_404(Controller, pk=controller_id)
    payload = {"action": "stop"} if request.POST.get("action") == "stop" else request.POST
    serializer = ManualSettingsSerializer(data=payload)
    if not serializer.is_valid():
        return JsonResponse({"errors": serializer.errors}, status=400)
    return action_response(apply_manual_action, controller_id, serializer.validated_data)
