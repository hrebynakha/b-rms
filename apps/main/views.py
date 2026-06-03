from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q

from apps.main.forms import BrewSessionForm, RecipeForm
from apps.main.models.brewery import Brewery
from apps.main.models.sensor import Sensor
from apps.main.models.recipe import Recipe, RecipeStep
from apps.main.models.session import BrewSession


def index(request):
    return render(request, "main/index.html")


def brewery_list_view(request):

    breweries = (
        Brewery.objects.prefetch_related(
            "controllers",
            "controllers__sensors",
            "controllers__sensors__telemetry",
        )
        .all()
        .order_by("-created_at")
    )

    return render(
        request,
        "main/brewery_list.html",
        {
            "breweries": breweries,
        },
    )


def sensor_detail_view(request, sensor_id):

    sensor = get_object_or_404(
        Sensor.objects.prefetch_related("telemetry"),
        id=sensor_id,
    )

    last_objects = sensor.telemetry.order_by("-created_at")[:50]

    # reverse for chart order
    data = list(reversed(last_objects))

    return render(
        request,
        "main/sensor_detail.html",
        {
            "sensor": sensor,
            "telemetry": data,
        },
    )


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

            for step_index, name in enumerate(names):

                if not name:
                    continue

                RecipeStep.objects.create(
                    recipe=recipe,
                    order=step_index + 1,
                    name=name,
                    target_temperature=float(temperatures[step_index]),
                    duration_minutes=int(durations[step_index]),
                )

            messages.success(request, "Recipe created successfully.")

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

            for i, name in enumerate(names):

                if not name:
                    continue

                RecipeStep.objects.create(
                    recipe=recipe,
                    order=i + 1,
                    name=name,
                    target_temperature=float(temps[i]),
                    duration_minutes=int(durations[i]),
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


def brew_session_list_view(request):

    sessions = BrewSession.objects.select_related(
        "brewery",
        "recipe",
    ).order_by("-created_at")

    return render(
        request,
        "main/brew_session_list.html",
        {
            "sessions": sessions,
        },
    )


def brew_session_create_view(request):

    if request.method == "POST":

        form = BrewSessionForm(request.POST)

        if form.is_valid():

            session = form.save()

            return redirect(
                "brew-session-detail",
                session.id,
            )

    else:
        form = BrewSessionForm()

    return render(
        request,
        "main/brew_session_form.html",
        {
            "form": form,
        },
    )


def brew_session_detail_view(
    request,
    session_id,
):

    session = get_object_or_404(
        BrewSession.objects.select_related(
            "recipe",
            "brewery",
        ),
        pk=session_id,
    )

    steps = session.recipe.steps.all()

    current_step = None

    if session.current_step_index < steps.count():
        current_step = steps[session.current_step_index]

    return render(
        request,
        "main/brew_session_detail.html",
        {
            "session": session,
            "steps": steps,
            "current_step": current_step,
        },
    )
