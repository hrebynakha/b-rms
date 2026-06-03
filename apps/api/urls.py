from django.urls import path
from apps.api.views import BootstrapView
from apps.api.views import TelemetryView

urlpatterns = [
    path("bootstrap/", BootstrapView.as_view(), name="bootstrap"),
    path("telemetry/", TelemetryView.as_view(), name="telemetry"),
]
