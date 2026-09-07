from functools import wraps
from django.shortcuts import redirect


def setup_required(view_func):
    """Wymaga ukończonego onboardingu (user musi mieć organizację)."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.organization_id:
            return redirect('accounts:setup')
        return view_func(request, *args, **kwargs)
    return wrapper
