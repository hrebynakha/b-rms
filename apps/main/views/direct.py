from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from apps.main.models import Controller, ManualControl
from apps.main.direct_messages import direct_messages


@require_GET
def direct_control_view(request, controller_id):
    controller = get_object_or_404(Controller, pk=controller_id)
    return render(request, 'main/direct_control.html', {'controller': controller, 'direct_messages': direct_messages()})
