from django.utils import timezone
from django.utils.text import slugify

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.main.models import Brewery
from apps.main.models import Controller
from apps.main.models import Sensor
from apps.main.models import Telemetry


from apps.api.serializers import TelemetrySerializer
from apps.api.serializers import BootstrapSerializer


class BootstrapView(APIView):

    authentication_classes = []
    permission_classes = []

    def post(self, request):

        serializer = BootstrapSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        controller = Controller.objects.filter(mac_address=data["mac_address"]).first()

        created = False

        if not controller:

            brewery = Brewery.objects.create(
                name=f"Brewery {data['mac_address']}",
                slug=slugify(data["mac_address"]),
            )

            controller = Controller.objects.create(
                brewery=brewery,
                mac_address=data["mac_address"],
                name=data["mac_address"],
                firmware_version=data.get(
                    "firmware_version",
                    "",
                ),
                ip=data.get(
                    "ip",
                    "",
                ),
            )
            created = True

        controller.last_seen_at = timezone.now()
        controller.firmware_version = data.get(
            "firmware_version",
            "",
        )
        controller.ip = data.get(
            "ip",
            "",
        )
        controller.save()
        # create sensors
        for sensor_data in data["sensors"]:

            Sensor.objects.get_or_create(
                controller=controller,
                key=sensor_data["key"],
                defaults={
                    "name": sensor_data["name"],
                    "kind": sensor_data["kind"],
                    "unit": sensor_data.get("unit", ""),
                },
            )

        return Response(
            {
                "controller_id": controller.id,
                "brewery_id": controller.brewery.id,
                "created": created,
            }
        )


class TelemetryView(APIView):

    authentication_classes = []
    permission_classes = []

    def post(self, request):

        serializer = TelemetrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        controller = Controller.objects.get(mac_address=data["mac_address"])

        controller.last_seen_at = timezone.now()
        controller.save(update_fields=["last_seen_at"])

        for key, value in data["metrics"].items():

            sensor = Sensor.objects.filter(
                controller=controller,
                key=key,
            ).first()

            if not sensor:
                continue

            Telemetry.objects.create(
                sensor=sensor,
                value=value,
            )

        return Response(
            {
                "success": True,
            }
        )
