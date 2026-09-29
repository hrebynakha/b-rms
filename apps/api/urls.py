from django.urls import path
from apps.api.views import BootstrapView
from apps.api.views import TelemetryView
from apps.api.views import BrewSessionStartView

urlpatterns = [
    path("bootstrap/", BootstrapView.as_view(), name="bootstrap"),
    path("telemetry/", TelemetryView.as_view(), name="telemetry"),
    path(
        "brew-sessions/<int:session_id>/start/",
        BrewSessionStartView.as_view(),
        name="api-brew-session-start",
    ),
]
