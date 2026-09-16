from django import forms

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
                    "placeholder": "Recipe name",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Description",
                }
            ),
        }


class BrewSessionForm(forms.ModelForm):

    class Meta:
        model = BrewSession

        fields = [
            "brewery",
            "recipe",
        ]


class BreweryDeleteForm(forms.Form):
    brewery_id = forms.IntegerField(widget=forms.HiddenInput())


class RecipeDeleteForm(forms.Form):
    recipe_id = forms.IntegerField(widget=forms.HiddenInput())
