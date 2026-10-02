from django.db import transaction
from django.utils.translation import gettext as _
from apps.main.direct_messages import direct_messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST
from apps.main.models import Controller, ManualControl
from apps.main.models.session import BrewSession, BrewSessionStatus
from apps.main.services.manual_control import control_state
from apps.main.manual_views import update_from_telemetry_if_unsafe


@require_GET
def direct_control_view(request, controller_id):
    controller = get_object_or_404(Controller, pk=controller_id)
    return render(request, 'main/direct_control.html', {'controller': controller, 'direct_messages': direct_messages()})


@require_GET
def direct_status_view(request, controller_id):
    controller = get_object_or_404(Controller, pk=controller_id)
    control, created = ManualControl.objects.get_or_create(controller=controller)
    update_from_telemetry_if_unsafe(control)
    response = JsonResponse(control_state(control))
    response['Cache-Control'] = 'no-store'
    return response


@require_POST
@transaction.atomic
def direct_action_view(request, controller_id):
    controller = get_object_or_404(Controller.objects.select_for_update(), pk=controller_id)
    ManualControl.objects.get_or_create(controller=controller)
    control = ManualControl.objects.select_for_update().get(controller=controller)
    output, value = request.POST.get('output'), request.POST.get('on')
    if output not in ('heater', 'pump', 'all') or value not in ('true', 'false') or (output == 'all' and value == 'true'):
        return JsonResponse({'detail': _('Invalid command.')}, status=400)
    on = value == 'true'
    if not control.direct_mode and control.active:
        return JsonResponse({'detail': _('Stop PID control first.')}, status=409)
    state = control_state(control)
    if on:
        if not state['live'] or not controller.is_enabled or controller.wifi_reset_command:
            return JsonResponse({'detail': _('Fresh sensor readings and an available controller are required.')}, status=409)
        if output == 'heater' and state['overheat']:
            return JsonResponse({'detail': _('Overheat: wait for cooling.')}, status=409)
        if BrewSession.objects.filter(brewery=controller.brewery, status__in=[
            BrewSessionStatus.RUNNING, BrewSessionStatus.HEATING,
            BrewSessionStatus.WAITING, BrewSessionStatus.PAUSED,
        ]).exists():
            return JsonResponse({'detail': _('Finish the active brew session first.')}, status=409)
    control.direct_mode = True
    if output in ('heater', 'all'):
        control.active = on
    if output in ('pump', 'all'):
        control.pump_on = on
    control.revision += 1
    control.save()
    return JsonResponse(control_state(control))
