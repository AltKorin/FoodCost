from django.conf import settings


def analytics(request):
    return {'GA_MEASUREMENT_ID': settings.GA_MEASUREMENT_ID}


def features(request):
    """Flags for templates: the Offers menu, the demo button, and the demo bar for a sandbox account."""
    org = getattr(getattr(request, 'user', None), 'organization', None) if getattr(request, 'user', None) and request.user.is_authenticated else None
    return {
        'OFFERS_ENABLED': settings.OFFERS_ENABLED,
        'DEMO_ENABLED': settings.DEMO_MAX > 0,
        'DEMO_UNTIL': org.demo_until if org else None,
    }
