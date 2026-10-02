from django.urls import path
from apps.main.direct_views import direct_control_view, direct_status_view, direct_action_view
from apps.main.settings_views import brewery_settings_view, controller_settings_view
from apps.main.manual_views import manual_control_view, manual_status_view, manual_action_view
from apps.main.views import (
    brewery_list_view,
    controller_reset_view,
    brewery_delete_view,
    sensor_detail_view,
    recipe_list_view,
    recipe_create_view,
    recipe_edit_view,
    recipe_delete_view,
    brew_session_detail_view,
    brew_session_list_view,
    brew_session_create_view,
    brew_session_delete_view,
    brew_session_cancel_view,
    sensor_cleanup_view,
)

urlpatterns = [
    path("brew-sessions/<int:session_id>/cancel/", brew_session_cancel_view, name="brew-session-cancel"),
    path("controllers/<int:controller_id>/direct/", direct_control_view, name="direct-control"),
    path("controllers/<int:controller_id>/direct/status/", direct_status_view, name="direct-status"),
    path("controllers/<int:controller_id>/direct/action/", direct_action_view, name="direct-action"),
    path("breweries/create/", brewery_settings_view, name="brewery-create"),
    path("breweries/<int:brewery_id>/settings/", brewery_settings_view, name="brewery-settings"),
    path("controllers/<int:controller_id>/settings/", controller_settings_view, name="controller-settings"),
    path("controllers/<int:controller_id>/manual/", manual_control_view, name="manual-control"),
    path("controllers/<int:controller_id>/manual/status/", manual_status_view, name="manual-status"),
    path("controllers/<int:controller_id>/manual/action/", manual_action_view, name="manual-action"),
    path("controllers/<int:controller_id>/reset/", controller_reset_view, name="controller-reset"),
    path(
        "",
        brewery_list_view,
        name="brewery-list",
    ),
    path(
        "breweries/delete/",
        brewery_delete_view,
        name="brewery-delete",
    ),
    path(
        "sensors/<int:sensor_id>/",
        sensor_detail_view,
        name="sensor-detail",
    ),
    path(
        "sensors/<int:sensor_id>/cleanup/",
        sensor_cleanup_view,
        name="sensor-cleanup",
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
    path(
        "recipes/delete/",
        recipe_delete_view,
        name="recipe-delete",
    ),
    path("recipes/<int:recipe_id>/edit/", recipe_edit_view, name="recipe-edit"),
    path("brew-sessions/", brew_session_list_view, name="brew-session-list"),
    path("brew-sessions/create/", brew_session_create_view, name="brew-session-create"),
    path("brew-sessions/delete/", brew_session_delete_view, name="brew-session-delete"),
    path(
        "brew-sessions/<int:session_id>/",
        brew_session_detail_view,
        name="brew-session-detail",
    ),
]
