from django import forms
from django.utils.translation import gettext_lazy as _

from apps.main.models.recipe import Recipe
from apps.main.models.session import BrewSession


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
