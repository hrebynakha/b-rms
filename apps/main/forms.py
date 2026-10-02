from django import forms
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.main.models.recipe import Recipe
from apps.main.models.session import BrewSession
from apps.main.models import Brewery, Controller, Vessel, ManualControl
from apps.main.models.session import BrewSessionStatus


class BrewerySettingsForm(forms.ModelForm):
    class Meta:
        model = Brewery
        fields = ["name", "location", "description"]
        labels = {"name": _("Brewery name"), "location": _("Location"), "description": _("Description")}
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class ControllerSettingsForm(forms.ModelForm):
    class Meta:
        model = Controller
        fields = ["name", "brewery"]
        labels = {"name": _("Controller name"), "brewery": _("Brewery")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_brewery_id = self.instance.brewery_id
        self.fields["name"].widget.attrs["class"] = "form-control"
        self.fields["brewery"].widget.attrs["class"] = "form-select"

    def clean_brewery(self):
        brewery = self.cleaned_data["brewery"]
        if brewery.pk != self.original_brewery_id:
            if ManualControl.objects.filter(Q(active=True) | Q(pump_on=True), controller=self.instance).exists():
                raise forms.ValidationError(_("Stop manual control before moving this controller."))
            if BrewSession.objects.filter(brewery_id__in=[brewery.pk, self.original_brewery_id], status__in=[
                BrewSessionStatus.RUNNING, BrewSessionStatus.HEATING,
                BrewSessionStatus.WAITING, BrewSessionStatus.PAUSED,
            ]).exists():
                raise forms.ValidationError(_("Finish active brew sessions before moving this controller."))
        return brewery


class VesselSettingsForm(forms.ModelForm):
    class Meta:
        model = Vessel
        fields = ["name", "volume_liters"]
        labels = {"name": _("Vessel name"), "volume_liters": _("Working volume (liters)")}
        widgets = {"name": forms.TextInput(attrs={"class": "form-control"}),
                   "volume_liters": forms.NumberInput(attrs={"class": "form-control", "min": .1, "step": .1})}


class RecipeForm(forms.ModelForm):
    class Meta:
        model = Recipe
        fields = [
            "name",
            "description",
        ]

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Recipe name"),
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": _("Description"),
                }
            ),
        }


class BrewSessionForm(forms.ModelForm):

    class Meta:
        model = BrewSession

        fields = [
            "brewery",
            "recipe",
            "mode",
        ]
        labels = {
            "brewery": _("Brewery"),
            "recipe": _("Recipe"),
            "mode": _("Timing mode"),
        }
        widgets = {
            "brewery": forms.Select(attrs={"class": "form-select form-select-lg"}),
            "recipe": forms.Select(attrs={"class": "form-select form-select-lg"}),
            "mode": forms.Select(attrs={"class": "form-select form-select-lg"}),
        }


class BreweryDeleteForm(forms.Form):
    brewery_id = forms.IntegerField(widget=forms.HiddenInput())


class RecipeDeleteForm(forms.Form):
    recipe_id = forms.IntegerField(widget=forms.HiddenInput())


class TelemetryCleanupForm(forms.Form):
    strategy = forms.ChoiceField(
        choices=[
            ("sessions", _("Keep the last N brew sessions")),
            ("minutes", _("Keep the last N minutes")),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    amount = forms.IntegerField(
        min_value=1,
        max_value=10080,
        initial=2,
        label=_("N"),
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
