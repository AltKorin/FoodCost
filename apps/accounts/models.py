import math
import uuid
from datetime import timedelta

from django.utils import timezone
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

    ocr_trial_started_at = models.DateTimeField('początek próby OCR', null=True, blank=True, editable=False)
    ocr_trial_pages_used = models.PositiveIntegerField('wykorzystane strony OCR', default=0, editable=False)
    ocr_access_requested_at = models.DateTimeField('zgłoszenie dalszego dostępu OCR', null=True, blank=True, editable=False)
    # Piaskownica z „Wypróbuj demo” (apps.core.demo): usuwana po tej chwili. Puste = prawdziwy lokal.
    demo_until = models.DateTimeField('demo do', null=True, blank=True, db_index=True, editable=False)

    OCR_TRIAL_DAYS = 30
    OCR_TRIAL_PAGES = 30

    @property
    def ocr_trial_ends_at(self):
        if self.ocr_trial_started_at:
            return self.ocr_trial_started_at + timedelta(days=self.OCR_TRIAL_DAYS)
        return None

    @property
    def ocr_trial_days_left(self):
        if not self.ocr_trial_ends_at:
            return self.OCR_TRIAL_DAYS
        return max(0, math.ceil((self.ocr_trial_ends_at - timezone.now()).total_seconds() / 86400))

    @property
    def ocr_trial_pages_left(self):
        return max(0, self.OCR_TRIAL_PAGES - self.ocr_trial_pages_used)

    @property
    def is_demo(self):
        """A visitor's sandbox or the presentation account (manage.py seed): the sample invoice is offered."""
        return bool(self.demo_until) or self.slug == 'demo'

    @property
    def ocr_available(self):
        if self.demo_until:  # every read costs money at OpenAI; the demo shows the rest of the app
            return False
        return self.plan == self.PLAN_PRO or (self.ocr_trial_days_left > 0 and self.ocr_trial_pages_left > 0)

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


class OCRRead(models.Model):
    """Rezerwacja stron przed wywołaniem API; nie przechowuje treści faktury."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='ocr_reads')
    pages = models.PositiveSmallIntegerField()
    trial = models.BooleanField(default=True)
    status = models.CharField(max_length=10, choices=[('pending', 'W trakcie'), ('success', 'Odczytano'), ('failed', 'Nieudany')], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['organization', 'status', 'created_at'])]
