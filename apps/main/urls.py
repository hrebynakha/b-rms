from django.urls import path
from apps.main.views import (
    brewery_list_view,
    sensor_detail_view,
    recipe_list_view,
    recipe_create_view,
    recipe_edit_view,
    brew_session_detail_view,
    brew_session_list_view,
    brew_session_create_view,
)

urlpatterns = [
    path(
        "",
        brewery_list_view,
        name="brewery-list",
    ),
    path(
        "sensors/<int:sensor_id>/",
        sensor_detail_view,
        name="sensor-detail",
    ),
    path(
        "recipes/",
        recipe_list_view,
        name="recipe-list",
    ),
    path(
        "recipes/create/",
        recipe_create_view,
        name="recipe-create",
    ),
    path("recipes/<int:recipe_id>/edit/", recipe_edit_view, name="recipe-edit"),
    path("brew-sessions/", brew_session_list_view, name="brew-session-list"),
    path("brew-sessions/create/", brew_session_create_view, name="brew-session-create"),
    path(
        "brew-sessions/<int:session_id>/",
        brew_session_detail_view,
        name="brew-session-detail",
    ),
]
