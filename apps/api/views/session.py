from django.utils.translation import gettext as _
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from apps.main.models.session import BrewSession
from apps.main.services.session_engine import SessionStartError, SessionStateError, pause_session, override_temperature, resume_session, start_session


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

