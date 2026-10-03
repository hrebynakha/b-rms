from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q
from django.utils.translation import gettext as _
from apps.main.forms import RecipeForm, RecipeDeleteForm
from apps.main.models.recipe import Recipe, RecipeStep
from apps.main.models.recipe import RecipeStepMode


def recipe_list_view(request):
    search = request.GET.get("search", "")

    recipes = Recipe.objects.all()

    if search:
        recipes = recipes.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )

    return render(
        request,
        "main/recipe_list.html",
        {
            "recipes": recipes,
            "search": search,
        },
    )



def recipe_create_view(request):

    if request.method == "POST":

        form = RecipeForm(request.POST)

        if form.is_valid():

            recipe = form.save()

            names = request.POST.getlist("step_name")
            temperatures = request.POST.getlist("step_temperature")
            durations = request.POST.getlist("step_duration")
            modes = request.POST.getlist("step_mode")

            for step_index, name in enumerate(names):

                if not name:
                    continue

                RecipeStep.objects.create(
                    recipe=recipe,
                    order=step_index + 1,
                    name=name,
                    target_temperature=float(temperatures[step_index]),
                    duration_minutes=int(durations[step_index]),
                    mode=modes[step_index] if step_index < len(modes) else RecipeStepMode.HOLD_TEMPERATURE,
                )

            messages.success(request, _("Recipe created successfully."))

            return redirect("recipe-list")

    else:
        form = RecipeForm()

    return render(
        request,
        "main/recipe_form.html",
        {
            "form": form,
        },
    )



def recipe_edit_view(request, recipe_id=None):

    recipe = None
    steps = []

    if recipe_id:
        recipe = get_object_or_404(Recipe, pk=recipe_id)
        steps = list(
            recipe.steps.all().values(
                "id",
                "name",
                "target_temperature",
                "duration_minutes",
                "mode",
                "order",
            )
        )

    if request.method == "POST":

        if recipe:
            form = RecipeForm(request.POST, instance=recipe)
        else:
            form = RecipeForm(request.POST)

        if form.is_valid():

            recipe = form.save()

            # clear old steps (simple MVP approach)
            recipe.steps.all().delete()

            names = request.POST.getlist("step_name")
            temps = request.POST.getlist("step_temperature")
            durations = request.POST.getlist("step_duration")
            modes = request.POST.getlist("step_mode")

            for i, name in enumerate(names):

                if not name:
                    continue

                RecipeStep.objects.create(
                    recipe=recipe,
                    order=i + 1,
                    name=name,
                    target_temperature=float(temps[i]),
                    duration_minutes=int(durations[i]),
                    mode=modes[i] if i < len(modes) else RecipeStepMode.HOLD_TEMPERATURE,
                )

            return redirect("recipe-list")

    else:

        form = RecipeForm(instance=recipe)

    return render(
        request,
        "main/recipe_form.html",
        {
            "form": form,
            "recipe": recipe,
            "is_edit": recipe is not None,
            "steps": steps,
        },
    )



def recipe_delete_view(request):

    if request.method == "POST":

        form = RecipeDeleteForm(request.POST)

        if form.is_valid():

            recipe = get_object_or_404(
                Recipe,
                id=form.cleaned_data["recipe_id"],
            )

            recipe.delete()

            messages.success(
                request,
                _("Recipe deleted successfully."),
            )

    return redirect("recipe-list")
