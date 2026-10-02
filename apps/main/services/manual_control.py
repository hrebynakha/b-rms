import math

from django.db import transaction
from django.utils import timezone

from apps.main.models import ManualControl, ManualControlSample, Telemetry
from apps.main.services.heating_estimate import heating_estimate

MAX_AGE_SECONDS = 10


def control_state(control, *, now=None):
    now = now or timezone.now()
    readings = list(Telemetry.objects.filter(
        sensor__controller=control.controller,
        sensor__key="mash_temperature_sensor", sensor__is_enabled=True,
    ).order_by("-created_at", "-pk")[:11])
    latest = readings[0] if readings else None
    temperature = latest.value if latest and math.isfinite(latest.value) else None
    live = bool(temperature is not None and 0 <= (now - latest.created_at).total_seconds() <= MAX_AGE_SECONDS)
    limit = control.warning_delta if control.warning_mode == "degrees" else control.target_temperature * control.warning_delta / 100
    overheat = bool(live and temperature >= control.target_temperature + limit)
    available = live and control.controller.is_enabled and not control.controller.wifi_reset_command
    report_fresh = bool(control.reported_at and control.reported_output_mode == ("direct" if control.direct_mode else "time_pwm") and
                        0 <= (now - control.reported_at).total_seconds() <= MAX_AGE_SECONDS)
    # PID lives on the ESP. Do not invent a duty from temperature on the server.
    power = control.reported_power if report_fresh else None
    ssr_on = control.reported_ssr_on if report_fresh else None
    previous = readings[1].value if len(readings) > 1 and math.isfinite(readings[1].value) else None
    delta = round(temperature - previous, 2) if temperature is not None and previous is not None else None
    status = "no_data" if not available else "overheat" if overheat else "stopped" if not control.active else "at_target" if temperature >= control.target_temperature else "heating"
    vessel = getattr(control.controller, "vessel", None)
    return {
        **heating_estimate(readings, control.target_temperature,
                           active=control.active, available=available and not overheat,
                           since=control.estimate_started_at),
        "vessel_name": vessel.name if vessel else control.controller.name,
        "volume_liters": float(vessel.volume_liters) if vessel else 20,
        "active": control.active, "target_temperature": control.target_temperature,
        "direct_mode": control.direct_mode, "pump_on": control.pump_on,
        "reported_pump_on": control.reported_pump_on if report_fresh else None,
        "pump_voltage": control.pump_voltage if report_fresh else None,
        "pump_current": control.pump_current if report_fresh else None,
        "temperature": temperature, "previous_temperature": previous, "delta": delta,
        "live": live, "temperature_at": latest.created_at.isoformat() if latest else None,
        "power_percent": power, "ssr_on": ssr_on,
        "signal_voltage": (3.3 if ssr_on else 0) if ssr_on is not None else None,
        "pid": {"kp": control.pid_kp, "ki": control.pid_ki, "kd": control.pid_kd},
        "window_ms": control.window_ms,
        "reported_window_ms": control.reported_window_ms if report_fresh else None,
        "on_time_ms": control.reported_on_time_ms if report_fresh else None,
        "output_confirmed": report_fresh and control.reported_revision == control.revision,
        "reported_enabled": control.reported_enabled if report_fresh else None,
        "reported_fault": control.reported_fault if report_fresh else False,
        "warning_delta": control.warning_delta, "warning_mode": control.warning_mode,
        "warning_temperature": round(control.target_temperature + limit, 2),
        "overheat": overheat, "status": status, "revision": control.revision,
        "reported_revision": control.reported_revision, "reported_power": control.reported_power,
        "reported_at": control.reported_at.isoformat() if control.reported_at else None,
        "simulation": False, "output_mode": "direct" if control.direct_mode else "time_pwm", "valid_for_ms": 10000,
        "reported_output_mode": control.reported_output_mode,
        "measured_voltage": control.measured_voltage,
    }


def record_sample(control, report=None):
    state = control_state(control)
    time_pwm = bool(report and report.get("output_mode") == "time_pwm")
    ssr_on = report.get("ssr_on") if time_pwm else None
    ManualControlSample.objects.create(
        control=control, temperature=state["temperature"],
        target_temperature=state["target_temperature"],
        power_percent=report["power_percent"] if time_pwm else None,
        signal_voltage=(3.3 if ssr_on else 0) if ssr_on is not None else None,
        ssr_on=ssr_on, output_mode="time_pwm" if time_pwm else "",
        measured_voltage=report.get("measured_voltage") if time_pwm and report.get("feedback_enabled") else None,
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
    if (control.active or control.pump_on) and (state["status"] == "no_data" or (control.active and state["overheat"])):
        control.active = False
        control.pump_on = False
        control.revision += 1
    if report:
        control.reported_revision = report["revision"]
        control.reported_power = report["power_percent"]
        control.reported_at = timezone.now()
        control.pump_voltage = report.get("pump_voltage")
        control.pump_current = report.get("pump_current")
        control.reported_output_mode = report.get("output_mode", "")
        time_pwm = report.get("output_mode") in ("time_pwm", "direct")
        control.reported_pump_on = report.get("pump_on") if time_pwm else None
        control.measured_voltage = report.get("measured_voltage") if time_pwm and report.get("feedback_enabled") else None
        control.reported_ssr_on = report.get("ssr_on") if time_pwm else None
        control.reported_window_ms = report.get("window_ms") if time_pwm else None
        control.reported_on_time_ms = report.get("on_time_ms") if time_pwm else None
        control.reported_enabled = report.get("enabled") if time_pwm else None
        control.reported_fault = report.get("fault", False) if time_pwm else False
        if (control.active or control.pump_on) and control.reported_fault and control.reported_revision == control.revision:
            control.active = False
            control.pump_on = False
            control.revision += 1
    control.save()
    record_sample(control, report)
