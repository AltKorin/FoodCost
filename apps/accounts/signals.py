from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from .models import LoginEvent


def _get_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    LoginEvent.objects.create(
        event_type=LoginEvent.LOGIN,
        user=user,
        username_attempted=user.username,
        ip_address=_get_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
    )


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    if user:
        LoginEvent.objects.create(
            event_type=LoginEvent.LOGOUT,
            user=user,
            username_attempted=user.username,
            ip_address=_get_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        )


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request, **kwargs):
    LoginEvent.objects.create(
        event_type=LoginEvent.FAILED,
        username_attempted=credentials.get('username', '')[:150],
        ip_address=_get_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
    )
