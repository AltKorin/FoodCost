"""Wspólny dla organizacji, odporny na równoległe wgrania limit próbny OCR."""
from datetime import timedelta
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from .models import Organization, OCRRead

RESERVATION_TTL = timedelta(minutes=5)


def pending_pages(organization):
    return OCRRead.objects.filter(
        organization=organization, trial=True, status='pending',
        created_at__gt=timezone.now() - RESERVATION_TTL,
    ).aggregate(total=Sum('pages'))['total'] or 0


@transaction.atomic
def reserve_read(organization_id, pages, request_id):
    if not 1 <= pages <= 10:
        raise ValueError('Możesz odczytać od 1 do 10 stron naraz.')
    org = Organization.objects.select_for_update().get(pk=organization_id)
    if OCRRead.objects.filter(pk=request_id).exists():
        raise ValueError('Ten odczyt został już wysłany. Poczekaj na wynik lub wybierz plik ponownie.')
    OCRRead.objects.filter(
        organization=org, status='pending', created_at__lte=timezone.now() - RESERVATION_TTL,
    ).update(status='failed')
    trial = org.plan != Organization.PLAN_PRO
    if trial:
        if org.ocr_trial_days_left == 0:
            raise ValueError('Okres próbny OCR zakończył się. Dane i ręczne dodawanie cen pozostają dostępne.')
        remaining = org.ocr_trial_pages_left - pending_pages(org)
        if pages > remaining:
            raise ValueError(f'Ten dokument ma {pages} str. Dostępne w próbie: {max(0, remaining)} str. (po uwzględnieniu odczytów w toku).')
    return OCRRead.objects.create(id=request_id, organization=org, pages=pages, trial=trial)


@transaction.atomic
def finish_read(read, *, success):
    org = Organization.objects.select_for_update().get(pk=read.organization_id)
    current = OCRRead.objects.select_for_update().get(pk=read.pk)
    if current.status != 'pending':
        if success:
            raise ValueError('Rezerwacja odczytu wygasła. Wgraj dokument ponownie.')
        return
    if success and current.trial:
        if org.ocr_trial_started_at is None:
            org.ocr_trial_started_at = timezone.now()
        org.ocr_trial_pages_used += current.pages
        org.save(update_fields=['ocr_trial_started_at', 'ocr_trial_pages_used'])
    current.status = 'success' if success else 'failed'
    current.save(update_fields=['status'])
