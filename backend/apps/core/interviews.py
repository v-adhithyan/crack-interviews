import subprocess
import time

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .auth import admin_api_required, user_from_authorization_header
from .executor import compile_java, run_measured_process
from .models import InterviewRoom, InterviewRoomShare


PERSONAL_EMAIL_DOMAINS = {
    "aol.com", "fastmail.com", "gmail.com", "googlemail.com", "gmx.com", "hey.com",
    "hotmail.com", "icloud.com", "live.com", "mail.com", "me.com", "mac.com",
    "msn.com", "outlook.com", "pm.me", "proton.me", "protonmail.com", "protonmail.ch",
    "yahoo.com", "yahoo.co.in", "yahoo.co.uk", "yahoo.ca", "yahoo.com.au", "yahoo.de", "yahoo.fr", "yandex.com",
}

MAX_CODE_LENGTH = 100000
MAX_INPUT_LENGTH = 50000
MAX_PROBLEM_LENGTH = 12000


def is_corporate_email(email):
    parts = (email or "").strip().lower().rsplit("@", 1)
    return len(parts) == 2 and bool(parts[0]) and bool(parts[1]) and parts[1] not in PERSONAL_EMAIL_DOMAINS


def can_host_interviews(user):
    return bool(user and user.is_superuser) or bool(user and is_corporate_email(user.email))


def can_interview(room, user):
    return user is not None and user.pk == room.interviewer_id and can_host_interviews(user)


def room_payload(room, viewer=None, reviewer=False):
    interviewer = can_interview(room, viewer)
    payload = {
        "id": str(room.uuid),
        "title": room.title,
        "problem_statement": room.problem_statement,
        "language": room.language,
        "code": room.code,
        "stdin": room.stdin,
        "candidate_name": room.candidate_name,
        "candidate_email": room.candidate_email,
        "candidate_joined": room.candidate_joined_at is not None,
        "interviewer_name": room.interviewer.get_full_name() or room.interviewer.email or room.interviewer.get_username(),
        "role": "interviewer" if interviewer else "reviewer" if reviewer else "candidate",
        "is_closed": room.is_closed,
        "updated_at": room.updated_at,
    }
    if interviewer:
        payload["hr_share_emails"] = list(room.hr_shares.values_list("email", flat=True))
    return payload


@api_view(["POST"])
@admin_api_required
def create_interview_room(request):
    user = request.admin_api_user
    if not can_host_interviews(user):
        return Response({"detail": "Only interviewers with a corporate email address can host an interview."}, status=status.HTTP_403_FORBIDDEN)
    title = request.data.get("title", "Problem solving interview")
    statement = request.data.get("problem_statement", "")
    language = request.data.get("language", "python")
    if not isinstance(title, str) or not title.strip() or len(title) > 160:
        return Response({"detail": "Add a title of up to 160 characters."}, status=status.HTTP_400_BAD_REQUEST)
    if not isinstance(statement, str) or len(statement) > MAX_PROBLEM_LENGTH:
        return Response({"detail": "The problem statement must be under 12,000 characters."}, status=status.HTTP_400_BAD_REQUEST)
    if language not in ("java", "python"):
        return Response({"detail": "Supported languages are java and python."}, status=status.HTTP_400_BAD_REQUEST)
    starter_code = "def solve():\n    pass\n\n" if language == "python" else "public class Main {\n    public static void main(String[] args) {\n        \n    }\n}\n"
    room = InterviewRoom.objects.create(interviewer=user, title=title.strip(), problem_statement=statement, language=language, code=starter_code)
    return Response(room_payload(room, user), status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH"])
def interview_room(request, room_uuid):
    room = InterviewRoom.objects.select_related("interviewer").filter(uuid=room_uuid).first()
    if room is None:
        return Response({"detail": "Interview room not found."}, status=status.HTTP_404_NOT_FOUND)
    viewer = user_from_authorization_header(request)
    is_interviewer = can_interview(room, viewer)
    if request.method == "GET":
        is_reviewer = bool(
            room.is_closed and viewer and room.hr_shares.filter(email__iexact=viewer.email).exists()
            and (viewer.email or "").casefold() != (room.candidate_email or "").casefold()
        )
        if room.is_closed and not is_interviewer and not is_reviewer:
            return Response({"detail": "This interview has ended and is no longer available."}, status=status.HTTP_410_GONE)
        return Response(room_payload(room, viewer, reviewer=is_reviewer))
    if room.is_closed:
        return Response({"detail": "This interview room is closed."}, status=status.HTTP_410_GONE)

    candidate_name = request.data.get("candidate_name")
    candidate_email = request.data.get("candidate_email")
    is_candidate_join = not is_interviewer and ("candidate_name" in request.data or "candidate_email" in request.data)
    if is_candidate_join:
        if not isinstance(candidate_name, str) or not candidate_name.strip() or len(candidate_name.strip()) > 100:
            return Response({"detail": "Enter a name under 100 characters to join."}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(candidate_email, str) or not candidate_email.strip() or len(candidate_email.strip()) > 254:
            return Response({"detail": "Enter a valid email address to join."}, status=status.HTTP_400_BAD_REQUEST)
        candidate_email = candidate_email.strip().lower()
        try:
            validate_email(candidate_email)
        except ValidationError:
            return Response({"detail": "Enter a valid email address to join."}, status=status.HTTP_400_BAD_REQUEST)
        if room.candidate_name:
            if candidate_name.strip().casefold() != room.candidate_name.casefold():
                return Response({"detail": "A candidate has already joined this interview link."}, status=status.HTTP_409_CONFLICT)
            if room.candidate_email and candidate_email != room.candidate_email.casefold():
                return Response({"detail": "A candidate has already joined this interview link."}, status=status.HTTP_409_CONFLICT)
            if not room.candidate_email:
                room.candidate_email = candidate_email
        else:
            room.candidate_name = candidate_name.strip()
            room.candidate_email = candidate_email
            room.candidate_joined_at = timezone.now()
    elif not is_interviewer and not room.candidate_joined_at:
        return Response({"detail": "Enter your name before editing the shared workspace."}, status=status.HTTP_409_CONFLICT)

    if "title" in request.data or "problem_statement" in request.data:
        if not is_interviewer:
            return Response({"detail": "Only the interviewer can edit the problem statement."}, status=status.HTTP_403_FORBIDDEN)
        title = request.data.get("title", room.title)
        statement = request.data.get("problem_statement", room.problem_statement)
        if not isinstance(title, str) or not title.strip() or len(title) > 160:
            return Response({"detail": "Add a title of up to 160 characters."}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(statement, str) or len(statement) > MAX_PROBLEM_LENGTH:
            return Response({"detail": "The problem statement must be under 12,000 characters."}, status=status.HTTP_400_BAD_REQUEST)
        room.title = title.strip()
        room.problem_statement = statement

    if "language" in request.data:
        if request.data["language"] not in ("java", "python"):
            return Response({"detail": "Supported languages are java and python."}, status=status.HTTP_400_BAD_REQUEST)
        room.language = request.data["language"]
    for field, limit in (("code", MAX_CODE_LENGTH), ("stdin", MAX_INPUT_LENGTH)):
        if field in request.data:
            value = request.data[field]
            if not isinstance(value, str) or len(value) > limit:
                return Response({"detail": f"{field} must be text under {limit:,} characters."}, status=status.HTTP_400_BAD_REQUEST)
            setattr(room, field, value)
    room.save()
    return Response(room_payload(room, viewer))


@api_view(["POST"])
@admin_api_required
def close_interview_room(request, room_uuid):
    if not can_host_interviews(request.admin_api_user):
        return Response({"detail": "Only a corporate email account can manage interview rooms."}, status=status.HTTP_403_FORBIDDEN)
    room = InterviewRoom.objects.filter(uuid=room_uuid, interviewer=request.admin_api_user).first()
    if room is None:
        return Response({"detail": "Interview room not found."}, status=status.HTTP_404_NOT_FOUND)
    if not room.is_closed:
        room.is_closed = True
        room.save(update_fields=("is_closed", "updated_at"))
    return Response(room_payload(room, request.admin_api_user))


@api_view(["POST"])
@admin_api_required
def share_interview_room(request, room_uuid):
    interviewer = request.admin_api_user
    if not can_host_interviews(interviewer):
        return Response({"detail": "Only a corporate email account can share interview rooms."}, status=status.HTTP_403_FORBIDDEN)
    room = InterviewRoom.objects.filter(uuid=room_uuid, interviewer=interviewer).first()
    if room is None:
        return Response({"detail": "Interview room not found."}, status=status.HTTP_404_NOT_FOUND)
    if not room.is_closed:
        return Response({"detail": "End the interview before sharing it with HR."}, status=status.HTTP_409_CONFLICT)
    email = request.data.get("email")
    if not isinstance(email, str) or len(email.strip()) > 254:
        return Response({"detail": "Enter a valid HR email address."}, status=status.HTTP_400_BAD_REQUEST)
    email = email.strip().casefold()
    try:
        validate_email(email)
    except ValidationError:
        return Response({"detail": "Enter a valid HR email address."}, status=status.HTTP_400_BAD_REQUEST)
    if email == (room.candidate_email or "").casefold():
        return Response({"detail": "The candidate cannot be granted access to their interview review."}, status=status.HTTP_400_BAD_REQUEST)
    InterviewRoomShare.objects.get_or_create(room=room, email=email)
    return Response(room_payload(room, interviewer))


@api_view(["POST"])
def run_interview_room(request, room_uuid):
    room = InterviewRoom.objects.filter(uuid=room_uuid).first()
    if room is None:
        return Response({"detail": "Interview room not found."}, status=status.HTTP_404_NOT_FOUND)
    viewer = user_from_authorization_header(request)
    is_interviewer = can_interview(room, viewer)
    if room.is_closed:
        return Response({"detail": "This interview room is closed."}, status=status.HTTP_410_GONE)
    if not is_interviewer and not room.candidate_joined_at:
        return Response({"detail": "Join the interview with your name before running code."}, status=status.HTTP_409_CONFLICT)

    language, code = room.language, room.code
    if not code.strip():
        return Response({"detail": "Add code before running it."}, status=status.HTTP_400_BAD_REQUEST)
    java_dir = None
    try:
        if language == "java":
            java_dir, class_name, compile_error, compile_ms = compile_java(code)
            if compile_error:
                return Response({"stdout": "", "stderr": compile_error, "execution_time_ms": compile_ms, "status": "compile_error"})
            command = [settings.JAVA_EXECUTABLE, "-cp", java_dir.name, class_name]
        else:
            command = [settings.PYTHON_EXECUTABLE, "-c", code]
        started = time.perf_counter()
        try:
            completed, _memory_kb = run_measured_process(command, room.stdin)
        except subprocess.TimeoutExpired as exc:
            output = exc.stdout or ""
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            return Response({"stdout": output[:20000], "stderr": "Execution timed out.", "execution_time_ms": int((time.perf_counter() - started) * 1000), "status": "time_limit_exceeded"})
        return Response({"stdout": completed.stdout[:20000], "stderr": completed.stderr[:20000],
                         "execution_time_ms": int((time.perf_counter() - started) * 1000),
                         "status": "completed" if completed.returncode == 0 else "runtime_error"})
    finally:
        if java_dir:
            java_dir.cleanup()
