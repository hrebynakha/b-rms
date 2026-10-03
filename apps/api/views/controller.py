from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.main.models import Controller
from apps.main.models import ManualControl
from apps.main.services.manual_control import control_state, update_from_telemetry
from apps.api.serializers import ControllerCommandSerializer, ControllerButtonSerializer
from apps.main.services.control_actions import apply_direct_action
from .control import action_response


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
            "active": False, "revision": 0, "simulation": False,
            "output_mode": "time_pwm", "valid_for_ms": 10000,
        }
        if control and (control.active or control.pump_on) and manual["status"] in ("no_data", "overheat"):
            update_from_telemetry(controller)
            control.refresh_from_db()
            manual = control_state(control)
        sessions = controller.brewery.brew_sessions.all()
        # A draft must not hide an active brew. Once idle, show the latest draft.
        session = sessions.filter(
            status__in=["running", "heating", "waiting_temperature", "paused"],
            started_at__isnull=False,
        ).order_by("-started_at", "-pk").first()
        if session is None:
            session = sessions.filter(status="pending", started_at__isnull=True).order_by("-created_at", "-pk").first()
        if session is None:
            session = sessions.filter(started_at__isnull=False).order_by("-started_at", "-pk").first()
        brew_state = None
        if session:
            brew_state = {
                "id": session.pk,
                "step_index": session.current_step_index,
                "status": session.status,
            }
        response = Response({"commands": commands, "manual_control": manual, "brew_session": brew_state})
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



class ControllerButtonView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = ControllerButtonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        controller = get_object_or_404(Controller, mac_address=data["mac_address"])
        return action_response(apply_direct_action, controller.pk, data["output"],
                                   "false" if data["output"] == "all" else "toggle")

