from functools import wraps

from django.conf import settings
from django.http import Http404
from django.urls import path

from . import views

app_name = 'offers'


def flagged(view):
    """Feature flag OFFERS_ENABLED: switched off, every Offers address answers 404 (CLAUDE.md: flags, not big bang)."""
    @wraps(view)
    def gated(request, *args, **kwargs):
        if not settings.OFFERS_ENABLED:
            raise Http404
        return view(request, *args, **kwargs)
    return gated


urlpatterns = [
    path('', flagged(views.offer_list), name='list'),
    path('new/', flagged(views.offer_edit), name='create'),
    path('<int:pk>/', flagged(views.offer_detail), name='detail'),
    path('<int:pk>/edit/', flagged(views.offer_edit), name='edit'),
    path('<int:pk>/print/', flagged(views.offer_print), name='print'),
]
