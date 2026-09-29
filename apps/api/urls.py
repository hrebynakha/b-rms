from django.urls import path
from apps.api.views import BootstrapView
from apps.api.views import TelemetryView
from apps.api.views import BrewSessionStartView
from apps.api.views import BrewSessionPauseView, BrewSessionResumeView

urlpatterns = [
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
]
