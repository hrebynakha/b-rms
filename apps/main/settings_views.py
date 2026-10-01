from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from apps.main.forms import BrewerySettingsForm, ControllerSettingsForm, VesselSettingsForm
from apps.main.models import Brewery, Controller, Vessel


@require_http_methods(["GET", "POST"])
def brewery_settings_view(request, brewery_id=None):
    brewery = get_object_or_404(Brewery, pk=brewery_id) if brewery_id else None
    form = BrewerySettingsForm(request.POST if request.method == "POST" else None, instance=brewery)
    if request.method == "POST" and form.is_valid():
        brewery = form.save()
        messages.success(request, _("Brewery settings saved."))
        return redirect("brewery-settings", brewery_id=brewery.pk)
    return render(request, "main/equipment_settings.html", {
        "title": _("Brewery settings") if brewery else _("Create brewery"),
        "forms": [form], "brewery": brewery,
        "controllers": brewery.controllers.select_related("vessel") if brewery else [],
    })


@require_http_methods(["GET", "POST"])
@transaction.atomic
def controller_settings_view(request, controller_id):
    controller = get_object_or_404(Controller.objects.select_for_update(), pk=controller_id)
    vessel, _created = Vessel.objects.get_or_create(controller=controller, defaults={"name": controller.name})
    data = request.POST if request.method == "POST" else None
    controller_form = ControllerSettingsForm(data, instance=controller, prefix="controller")
    vessel_form = VesselSettingsForm(data, instance=vessel, prefix="vessel")
    if request.method == "POST":
        valid_controller = controller_form.is_valid()
        valid_vessel = vessel_form.is_valid()
        if valid_controller and valid_vessel:
            controller = controller_form.save(commit=False)
            controller.save(update_fields=["name", "brewery"])
            vessel_form.save()
            messages.success(request, _("Vessel and controller settings saved."))
            return redirect("controller-settings", controller_id=controller.pk)
    return render(request, "main/equipment_settings.html", {
        "title": _("Vessel settings"), "forms": [controller_form, vessel_form],
        "controller": controller,
    })
