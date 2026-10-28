"""Restauracja Demo z przykładowymi składnikami, dostawcami, przepisami i pakietem weselnym (apps.core.demo).

Hasło konta demo tylko z DEMO_PASSWORD w .env — na serwerze (DEBUG=False) bez niego komenda odmawia,
bo hasło zapisane w kodzie otwierałoby konto każdemu, kto zna repozytorium. Idempotentna."""
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Organization, User
from apps.core import demo

DEMO_EMAIL = 'demo@fc.sudomie.pl'


class Command(BaseCommand):
    help = 'Zasiewa Restaurację Demo z przykładowymi składnikami, dostawcami, przepisami i pakietem weselnym.'

    @transaction.atomic
    def handle(self, *args, **options):
        password = os.environ.get('DEMO_PASSWORD')
        if not password and not settings.DEBUG:
            raise CommandError('Ustaw DEMO_PASSWORD w .env (długie, losowe) — bez niego demo działa tylko lokalnie (DJANGO_DEBUG=True).')
        if Organization.objects.filter(slug='demo').exists():
            self.stdout.write('Restauracja Demo już jest — nic nie zmieniono.')
            return
        org = demo.fill(Organization.objects.create(name=demo.NAME, slug='demo', accepted_tos_at=timezone.now()))
        user = User.objects.create_user(username=DEMO_EMAIL, email=DEMO_EMAIL, organization=org, role=User.ROLE_OWNER)
        user.set_password(password or 'demo-haslo-tylko-lokalnie')
        user.save()
        self.stdout.write(self.style.SUCCESS(f'Zasiano „{org.name}”. Login: {DEMO_EMAIL}, hasło: DEMO_PASSWORD z .env.'))
