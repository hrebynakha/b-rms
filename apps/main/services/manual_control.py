import math

from django.db import transaction
from django.utils import timezone

from apps.main.models import ManualControl, ManualControlSample, Telemetry

MAX_AGE_SECONDS = 10


def control_state(control, *, now=None):
    now = now or timezone.now()
    readings = list(Telemetry.objects.filter(
        sensor__controller=control.controller,
        sensor__key="mash_temperature_sensor", sensor__is_enabled=True,
    ).order_by("-created_at", "-pk")[:2])
    latest = readings[0] if readings else None
    temperature = latest.value if latest and math.isfinite(latest.value) else None
    live = bool(temperature is not None and 0 <= (now - latest.created_at).total_seconds() <= MAX_AGE_SECONDS)
    limit = control.warning_delta if control.warning_mode == "degrees" else control.target_temperature * control.warning_delta / 100
    overheat = bool(live and temperature >= control.target_temperature + limit)
    available = live and control.controller.is_enabled and not control.controller.wifi_reset_command
    power = 0.0
    if control.active and available and not overheat:
        # Proportional request: full power at a deficit of 10 C, zero at target.
        power = round(min(100, max(0, (control.target_temperature - temperature) * 10)), 1)
    previous = readings[1].value if len(readings) > 1 and math.isfinite(readings[1].value) else None
    delta = round(temperature - previous, 2) if temperature is not None and previous is not None else None
    status = "no_data" if not available else "overheat" if overheat else "stopped" if not control.active else "heating" if power else "at_target"
    return {
        "active": control.active, "target_temperature": control.target_temperature,
        "temperature": temperature, "previous_temperature": previous, "delta": delta,
        "live": live, "temperature_at": latest.created_at.isoformat() if latest else None,
        "power_percent": power, "signal_voltage": round(power * 3.3 / 100, 3),
        "warning_delta": control.warning_delta, "warning_mode": control.warning_mode,
        "warning_temperature": round(control.target_temperature + limit, 2),
        "overheat": overheat, "status": status, "revision": control.revision,
        "reported_revision": control.reported_revision, "reported_power": control.reported_power,
        "reported_at": control.reported_at.isoformat() if control.reported_at else None,
        "simulation": False, "output_mode": "pwm", "valid_for_ms": 10000,
        "reported_output_mode": control.reported_output_mode,
        "measured_voltage": control.measured_voltage,
    }


def record_sample(control, measured_voltage=None):
    state = control_state(control)
    ManualControlSample.objects.create(
        control=control, temperature=state["temperature"],
        target_temperature=state["target_temperature"],
        power_percent=state["power_percent"], signal_voltage=state["signal_voltage"],
        measured_voltage=measured_voltage,
    )
    # Keep a bounded recent chart (roughly one hour at three-second telemetry).
    cutoff = control.samples.order_by("-pk").values_list("pk", flat=True)[1200:1201]
    if cutoff:
        control.samples.filter(pk__lte=cutoff[0]).delete()


@transaction.atomic
def update_from_telemetry(controller, report=None):
    control = ManualControl.objects.select_for_update().filter(controller=controller).first()
    if not control:
        return
    state = control_state(control)
    if control.active and state["status"] in ("no_data", "overheat"):
        control.active = False
        control.revision += 1
    if report:
        control.reported_revision = report["revision"]
        control.reported_power = report["power_percent"]
        control.reported_at = timezone.now()
        control.reported_output_mode = report.get("output_mode", "")
        control.measured_voltage = report.get("measured_voltage") if report.get("feedback_enabled") and report.get("output_mode") == "pwm" else None
    control.save()
    record_sample(control, control.measured_voltage if report else None)
