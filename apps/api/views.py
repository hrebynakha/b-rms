from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from django.utils.text import slugify
from django.utils.translation import gettext as _

from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from apps.main.models import Brewery
from apps.main.models import Controller
from apps.main.models import Sensor
from apps.main.models import Telemetry
from apps.main.models import ManualControl
from apps.main.services.manual_control import control_state, update_from_telemetry


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


class ControllerCommandSerializer(serializers.Serializer):
    mac_address = serializers.CharField()
    command_id = serializers.UUIDField(required=False)


class ControllerCommandsView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        serializer = ControllerCommandSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        controller = get_object_or_404(Controller, mac_address=serializer.validated_data["mac_address"])
        commands = []
        if controller.wifi_reset_command:
            commands.append({"id": str(controller.wifi_reset_command), "type": "wifi_setup"})
        control = ManualControl.objects.filter(controller=controller).first()
        manual = control_state(control) if control else {
            "active": False, "power_percent": 0, "signal_voltage": 0,
            "revision": 0, "simulation": False, "output_mode": "pwm", "valid_for_ms": 10000,
        }
        if control and control.active and manual["status"] in ("no_data", "overheat"):
            update_from_telemetry(controller)
            control.refresh_from_db()
            manual = control_state(control)
        response = Response({"commands": commands, "manual_control": manual})
        response["Cache-Control"] = "no-store"
        return response

    def post(self, request):
        serializer = ControllerCommandSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if "command_id" not in data:
            return Response({"detail": _("command_id is required.")}, status=400)
        controller = get_object_or_404(Controller, mac_address=data["mac_address"])
        updated = Controller.objects.filter(
            pk=controller.pk, wifi_reset_command=data["command_id"]
        ).update(wifi_reset_command=None)
        # A retry after a lost acknowledgement response must still allow setup.
        if not updated and Controller.objects.filter(pk=controller.pk, wifi_reset_command__isnull=False).exists():
            return Response({"detail": _("Command is no longer pending.")}, status=409)
        return Response({"success": True})


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

        update_from_telemetry(controller, data.get("manual_control"))
        return Response({"success": True})


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
