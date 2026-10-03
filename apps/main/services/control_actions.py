from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.main.models import Controller, ManualControl
from apps.main.models.session import BrewSession, BrewSessionStatus
from apps.main.services.manual_control import control_state, record_sample, update_from_telemetry


class ControlActionError(Exception):
    def __init__(self, detail, status=409):
        super().__init__(detail)
        self.status = status


def update_from_telemetry_if_unsafe(control):
    if (control.active or control.pump_on) and control_state(control)["status"] in ("no_data", "overheat"):
        update_from_telemetry(control.controller)
        control.refresh_from_db()



@transaction.atomic
def apply_direct_action(controller_id, output, value):
    controller = Controller.objects.select_for_update().get(pk=controller_id)
    ManualControl.objects.get_or_create(controller=controller)
    control = ManualControl.objects.select_for_update().get(controller=controller)
    if value == 'toggle' and output in ('heater', 'pump'):
        value = 'false' if (control.active if output == 'heater' else control.pump_on) else 'true'
    if output not in ('heater', 'pump', 'all') or value not in ('true', 'false') or (output == 'all' and value == 'true'):
        raise ControlActionError(_('Invalid command.'), status=400)
    on = value == 'true'
    stop_all = output == 'all' and not on
    if not stop_all and not control.direct_mode and control.active:
        raise ControlActionError(_('Stop PID control first.'), status=409)
    state = control_state(control)
    if on:
        if not state['live'] or not controller.is_enabled or controller.wifi_reset_command:
            raise ControlActionError(_('Fresh sensor readings and an available controller are required.'), status=409)
        if output == 'heater' and state['overheat']:
            raise ControlActionError(_('Overheat: wait for cooling.'), status=409)
        if BrewSession.objects.filter(brewery=controller.brewery, status__in=[
            BrewSessionStatus.RUNNING, BrewSessionStatus.HEATING,
            BrewSessionStatus.WAITING, BrewSessionStatus.PAUSED,
        ]).exists():
            raise ControlActionError(_('Finish the active brew session first.'), status=409)
    if not stop_all:
        control.direct_mode = True
    if output in ('heater', 'all'):
        control.active = on
    if output in ('pump', 'all'):
        control.pump_on = on
    control.revision += 1
    control.save()
    return control_state(control)



@transaction.atomic
def apply_manual_action(controller_id, data):
    controller = Controller.objects.get(pk=controller_id)
    ManualControl.objects.get_or_create(controller=controller)
    control = ManualControl.objects.select_for_update().get(controller=controller)
    data = dict(data)
    action = data.pop("action")
    if action != "stop" and control.direct_mode and (control.active or control.pump_on):
        raise ControlActionError(_("Stop direct control first."), status=409)
    control.direct_mode = False
    control.pump_on = False
    if action != "stop":
        for key, value in data.items():
            setattr(control, key, value)
        state = control_state(control)
        if action == "start" or control.active:
            if not state["live"] or not controller.is_enabled or controller.wifi_reset_command:
                raise ControlActionError(_("Fresh sensor readings and an available controller are required."), status=409)
            if state["overheat"]:
                raise ControlActionError(_("The temperature exceeds the overheat threshold. Wait for cooling."), status=409)
            if BrewSession.objects.filter(brewery=controller.brewery, status__in=[
                BrewSessionStatus.RUNNING, BrewSessionStatus.HEATING,
                BrewSessionStatus.WAITING, BrewSessionStatus.PAUSED,
            ]).exists():
                raise ControlActionError(_("Finish the active brew session first."), status=409)
        if action == "start":
            control.active = True
        control.estimate_started_at = timezone.now()
    else:
        control.active = False
    control.revision += 1
    control.save()
    chart_since = timezone.now()
    record_sample(control)
    state = control_state(control)
    if action in ("start", "apply"):
        state["chart_since"] = chart_since.isoformat()
    return state
