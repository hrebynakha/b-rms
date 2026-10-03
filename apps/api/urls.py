from apps.api.views import direct_status_view, direct_action_view, manual_status_view, manual_action_view
from django.urls import path
from apps.api.views import ControllerButtonView
from apps.api.views import BootstrapView
from apps.api.views import ControllerCommandsView
from apps.api.views import TelemetryView
from apps.api.views import BrewSessionStartView
from apps.api.views import BrewSessionPauseView, BrewSessionResumeView
from apps.api.views import BrewSessionTemperatureOverrideView

urlpatterns = [
    path("controllers/<int:controller_id>/direct/status/", direct_status_view, name="direct-status"),
    path("controllers/<int:controller_id>/direct/action/", direct_action_view, name="direct-action"),
    path("controllers/<int:controller_id>/manual/status/", manual_status_view, name="manual-status"),
    path("controllers/<int:controller_id>/manual/action/", manual_action_view, name="manual-action"),
    path("button/", ControllerButtonView.as_view(), name="controller-button"),
    path("commands/", ControllerCommandsView.as_view(), name="controller-commands"),
    path("bootstrap/", BootstrapView.as_view(), name="bootstrap"),
    path("telemetry/", TelemetryView.as_view(), name="telemetry"),
    path(
        "brew-sessions/<int:session_id>/start/",
        BrewSessionStartView.as_view(),
        name="api-brew-session-start",
    ),
    path(
        "brew-sessions/<int:session_id>/pause/",
        BrewSessionPauseView.as_view(),
        name="api-brew-session-pause",
    ),
    path(
        "brew-sessions/<int:session_id>/resume/",
        BrewSessionResumeView.as_view(),
        name="api-brew-session-resume",
    ),
    path(
        "brew-sessions/<int:session_id>/temperature-override/",
        BrewSessionTemperatureOverrideView.as_view(),
        name="api-brew-session-temperature-override",
    ),
]
