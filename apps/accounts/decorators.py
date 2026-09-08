from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect


def setup_required(view_func):
    """Wymaga ukończonego onboardingu (user musi mieć organizację)."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.organization_id:
            return redirect('accounts:setup')
        return view_func(request, *args, **kwargs)
    return wrapper


def pro_required(view_func):
    """Wymaga planu Pro — funkcje z kosztem po naszej stronie (np. OCR faktur,
    które płaci się za token AI). Wymaga @setup_required wcześniej w łańcuchu."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from apps.accounts.models import Organization
        if request.user.organization.plan != Organization.PLAN_PRO:
            messages.info(request, 'Ta funkcja jest dostępna w planie Pro. Napisz do nas, żeby ją odblokować.')
            return redirect('core:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper
