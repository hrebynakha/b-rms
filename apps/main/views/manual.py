from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from apps.main.models import Controller, ManualControl
from apps.main.manual_messages import manual_messages


@require_GET
def manual_control_view(request, controller_id):
    controller = get_object_or_404(Controller, pk=controller_id)
    control, _ = ManualControl.objects.get_or_create(controller=controller)
    return render(request, "main/manual_control.html", {
        "controller": controller, "control": control, "manual_messages": manual_messages(),
    })
