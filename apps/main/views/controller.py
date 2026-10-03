from uuid import uuid4
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils.translation import gettext as _
from apps.main.models import Controller


@require_POST
def controller_reset_view(request, controller_id):
    controller = get_object_or_404(Controller, pk=controller_id)
    Controller.objects.filter(pk=controller.pk, wifi_reset_command__isnull=True).update(
        wifi_reset_command=uuid4()
    )
    messages.success(request, _("Wi-Fi setup command queued. Waiting for the controller."))
    return redirect("brewery-list")
