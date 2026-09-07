from django.contrib.auth.models import AbstractUser
from django.db import models
from simple_history.models import HistoricalRecords


class Organization(models.Model):
    PLAN_FREE = 'free'
    PLAN_PRO = 'pro'
    PLAN_CHOICES = [(PLAN_FREE, 'Free'), (PLAN_PRO, 'Pro')]

    name = models.CharField('nazwa', max_length=200)
    slug = models.SlugField(unique=True)
    plan = models.CharField(max_length=10, choices=PLAN_CHOICES, default=PLAN_FREE)
    accepted_tos_at = models.DateTimeField('akceptacja regulaminu', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'organizacja'
        verbose_name_plural = 'organizacje'
        ordering = ['name']

    def __str__(self):
        return self.name


class User(AbstractUser):
    ROLE_OWNER = 'owner'
    ROLE_ADMIN = 'admin'
    ROLE_CHEF = 'chef'
    ROLE_VIEWER = 'viewer'
    ROLE_CHOICES = [
        (ROLE_OWNER, 'Właściciel'),
        (ROLE_ADMIN, 'Administrator'),
        (ROLE_CHEF, 'Szef kuchni'),
        (ROLE_VIEWER, 'Podgląd'),
    ]

    organization = models.ForeignKey(
        Organization,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='users',
        verbose_name='organizacja',
    )
    role = models.CharField(
        'rola',
        max_length=10,
        choices=ROLE_CHOICES,
        default=ROLE_VIEWER,
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'użytkownik'
        verbose_name_plural = 'użytkownicy'

    def __str__(self):
        return self.email or self.username

    @property
    def is_org_admin(self):
        return self.role in (self.ROLE_OWNER, self.ROLE_ADMIN)


class LoginEvent(models.Model):
    LOGIN = 'login'
    LOGOUT = 'logout'
    FAILED = 'failed'
    EVENT_CHOICES = [
        (LOGIN, 'Logowanie'),
        (LOGOUT, 'Wylogowanie'),
        (FAILED, 'Nieudana próba'),
    ]

    event_type = models.CharField(max_length=10, choices=EVENT_CHOICES)
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='login_events',
    )
    username_attempted = models.CharField(max_length=150, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'zdarzenie logowania'
        verbose_name_plural = 'zdarzenia logowania'
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.event_type} — {self.username_attempted or self.user} — {self.timestamp:%Y-%m-%d %H:%M}'

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionError("LoginEvent jest niemutowalny — nie można edytować.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("LoginEvent nie może być usunięty.")
