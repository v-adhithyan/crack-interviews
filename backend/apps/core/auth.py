from functools import wraps

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from .models import AdminApiToken


def user_from_authorization_header(request):
    authorization = request.headers.get("Authorization", "")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return None

    token_value = authorization.removeprefix(prefix).strip()
    token = AdminApiToken.objects.select_related("user").filter(token=token_value, user__is_active=True, user__is_staff=True).first()
    if not token:
        return None

    token.last_used_at = timezone.now()
    token.save(update_fields=["last_used_at"])
    return token.user


def admin_api_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        user = user_from_authorization_header(request)
        if user is None:
            return Response({"detail": "Admin login is required."}, status=status.HTTP_401_UNAUTHORIZED)
        request.admin_api_user = user
        return view_func(request, *args, **kwargs)

    return wrapped
