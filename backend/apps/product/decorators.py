from functools import wraps

from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import AccessMixin
from django.contrib.auth.views import redirect_to_login


def user_has_product_access(user):
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return user.early_access_invite.is_beta_active if hasattr(user, "early_access_invite") else False


def product_access_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not user_has_product_access(request.user):
            raise PermissionDenied

        return view_func(request, *args, **kwargs)


    return wrapped


class ProductAccessMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not user_has_product_access(request.user):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)
