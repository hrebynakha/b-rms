from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext as _

from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from apps.main.models import Brewery
from apps.main.models import Controller
from apps.main.models import Sensor
from apps.main.models import Telemetry


from apps.api.serializers import TelemetrySerializer
from apps.api.serializers import BootstrapSerializer
from apps.main.models.session import BrewSession
from apps.main.services.session_engine import (
    SessionStartError,
    SessionStateError,
    pause_session,
    override_temperature,
    resume_session,
    start_session,
)


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
                print("Sensor not found")
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


class BrewSessionStartView(APIView):

    def post(self, request, session_id):
        try:
            session, progress = start_session(session_id)
        except BrewSession.DoesNotExist:
            return Response(
                {"detail": _("Brew session not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )
        except SessionStartError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                "id": session.id,
                "status": session.status,
                "started_at": session.started_at,
                "current_step_index": progress.step_index,
                "current_step": progress.step_name,
                "current_step_number": progress.step_number,
                "total_steps": progress.total_steps,
                "step_remaining_seconds": progress.step_remaining_seconds,
                "remaining_seconds": progress.remaining_seconds,
                "progress_percent": progress.percent,
                "waiting_for_temperature": progress.waiting_for_temperature,
                "target_temperature": progress.target_temperature,
                "current_temperature": progress.current_temperature,
            },
            status=status.HTTP_200_OK,
        )


class BrewSessionPauseView(APIView):
    def post(self, request, session_id):
        return _change_session_state(pause_session, session_id)


class BrewSessionResumeView(APIView):
    def post(self, request, session_id):
        return _change_session_state(resume_session, session_id)


class BrewSessionTemperatureOverrideView(APIView):
    def post(self, request, session_id):
        return _change_session_state(override_temperature, session_id)


def _change_session_state(action, session_id):
    try:
        session, progress = action(session_id)
    except BrewSession.DoesNotExist:
        return Response(
            {"detail": _("Brew session not found.")},
            status=status.HTTP_404_NOT_FOUND,
        )
    except SessionStateError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
    return Response(
        {
            "id": session.id,
            "status": session.status,
            "remaining_seconds": progress.remaining_seconds,
            "progress_percent": progress.percent,
            "waiting_for_temperature": progress.waiting_for_temperature,
            "target_temperature": progress.target_temperature,
            "current_temperature": progress.current_temperature,
        }
    )
