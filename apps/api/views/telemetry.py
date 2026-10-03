from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.main.models import Controller
from apps.main.models import Telemetry
from apps.main.services.manual_control import update_from_telemetry
from apps.api.serializers import TelemetrySerializer


class TelemetryView(APIView):

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = TelemetrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        controller = get_object_or_404(Controller, mac_address=data["mac_address"])

        controller.last_seen_at = timezone.now()
        controller.save(update_fields=["last_seen_at"])

        sensors = {sensor.key: sensor for sensor in controller.sensors.filter(key__in=data["metrics"])}
        Telemetry.objects.bulk_create([
            Telemetry(sensor=sensors[key], value=value)
            for key, value in data["metrics"].items() if key in sensors
        ])

        update_from_telemetry(controller, data.get("manual_control"))
        return Response({"success": True})

