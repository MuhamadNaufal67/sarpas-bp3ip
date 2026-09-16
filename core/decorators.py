from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def role_required(*roles):
    """Batasi view untuk satu atau beberapa role user."""
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if request.user.role not in roles:
                messages.error(request, "Anda tidak memiliki akses ke halaman tersebut.")
                return redirect("dashboard")
            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator
