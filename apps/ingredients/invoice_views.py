"""Widoki OCR faktur — wgraj (PDF/zdjęcie) → potwierdź dopasowania → zapisz ceny.

Dostęp próbny OCR: 30 dni i 30 stron na organizację. Istniejący plan Pro pozostaje aktywny.
"""
import uuid
import re
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.shortcuts import render, get_object_or_404, redirect

from apps.accounts.decorators import setup_required
from apps.accounts.models import Organization
from apps.accounts.ocr_access import reserve_read, finish_read, pending_pages
from .models import Ingredient, Supplier, SupplierPrice, UNIT_CHOICES
from .ocr_service import (
    extract_invoice_data, extract_invoice_data_from_image,
    normalize_items, fuzzy_match_ingredients, SUPPORTED_IMAGE_EXTENSIONS, inspect_invoice_file,
)


def _match_supplier(name, suppliers_qs):
    """Dopasowuje nazwę dostawcy z faktury do istniejących Supplier po
    overlapie słów — ten sam pomysł co fuzzy_match_ingredients, tylko na
    pojedynczą nazwę zamiast listy pozycji."""
    if not name:
        return None
    name_words = set(re.findall(r'\w{3,}', name.lower()))
    if not name_words:
        return None
    best, best_score = None, 0
    for s in suppliers_qs:
        s_words = set(re.findall(r'\w{3,}', s.name.lower()))
        if not s_words:
            continue
        score = len(name_words & s_words) / len(name_words)
        if score > best_score and score >= 0.5:
            best_score = score
            best = s
    return best


def _remember_read(request, org, raw_data, supplier=None, sample=False):
    """An OCR result (or the demo's sample) → matched to this kitchen's ingredients → the confirm step in the session."""
    items = normalize_items(raw_data.get('items', []))
    if not items:
        raise ValueError('Nie znaleziono pozycji w fakturze. Sprawdź czytelność pliku. Nie odjęliśmy stron z limitu.')
    items = fuzzy_match_ingredients(items, Ingredient.objects.filter(organization=org, is_active=True))
    supplier_name = raw_data.get('supplier_name')
    if not supplier:
        supplier = _match_supplier(supplier_name, Supplier.objects.filter(organization=org))
    request.session['invoice_items'] = [
        {
            'name': i['name'], 'price': str(i['price']),
            'price_per_unit': str(i['price_per_unit']), 'unit': i['unit'],
            'package_size': str(i['package_size']) if i['package_size'] else None,
            'vat': i['vat'], 'is_netto': i['is_netto'],
            'purchased_quantity': i.get('purchased_quantity'),
            'matched_ingredient_id': i['matched_ingredient'].pk if i['matched_ingredient'] else None,
            'matched_ingredient_name': i['matched_ingredient'].name if i['matched_ingredient'] else None,
            'match_score': round(i['match_score'], 2),
        } for i in items
    ]
    request.session['invoice_supplier_id'] = supplier.pk if supplier else None
    request.session['invoice_meta'] = {
        'supplier_name': supplier_name, 'invoice_number': raw_data.get('invoice_number'),
        'invoice_date': raw_data.get('invoice_date'), 'warnings': raw_data.get('warnings', []), 'sample': sample,
    }


@login_required
@setup_required
@require_POST
def invoice_sample(request):
    """Demo only: the sample invoice goes through the real matching and confirm step, without OCR (no OpenAI cost)."""
    from apps.core.demo import sample_invoice

    org = request.user.organization
    if not org.is_demo:
        raise Http404
    _remember_read(request, org, sample_invoice(), sample=True)
    return redirect('ingredients:invoice-confirm')


def _upload_context(org):
    org.refresh_from_db()
    return {
        'suppliers': Supplier.objects.filter(organization=org),
        'ocr_org': org,
        'ocr_reserved': pending_pages(org),
        'request_id': str(uuid.uuid4()),
        'sample_invoice': _sample_preview() if org.is_demo else None,
    }


def _sample_preview():
    from apps.core.demo import sample_invoice

    raw = sample_invoice()
    return {**raw, 'items': normalize_items(raw['items'])}


@login_required
@setup_required
@require_POST
def invoice_estimate(request):
    """Sprawdza dokument i pokazuje koszt w stronach, bez startowania próby."""
    try:
        _, _, pages = inspect_invoice_file(request.FILES.get('invoice_file'))
        org = request.user.organization
        available = max(0, org.ocr_trial_pages_left - pending_pages(org))
        pro = org.plan == Organization.PLAN_PRO
        return JsonResponse({
            'pages': pages, 'available': available, 'pro': pro,
            'allowed': pro or (org.ocr_trial_days_left > 0 and pages <= available),
        })
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)


@login_required
@setup_required
@require_POST
def invoice_request_access(request):
    Organization.objects.filter(pk=request.user.organization_id, ocr_access_requested_at__isnull=True).update(ocr_access_requested_at=timezone.now())
    messages.success(request, 'Zapisaliśmy zainteresowanie dalszym dostępem do OCR. Nie naliczyliśmy żadnej opłaty.')
    return redirect('ingredients:invoice-upload')


@login_required
@setup_required
def invoice_upload(request):
    """Pierwszy udany odczyt uruchamia 30 dni; limit jest wspólny dla lokalu."""
    org = request.user.organization
    read = None
    completed = False
    if request.method == 'POST':
        try:
            supplier_id = request.POST.get('supplier_id')
            if supplier_id:
                supplier = get_object_or_404(Supplier, pk=supplier_id, organization=org)
            file_bytes, file_ext, pages = inspect_invoice_file(request.FILES.get('invoice_file'))
            try:
                request_id = uuid.UUID(request.POST.get('request_id', ''))
            except (ValueError, TypeError, AttributeError) as exc:
                raise ValueError('Odśwież formularz i wybierz plik ponownie.') from exc
            read = reserve_read(org.pk, pages, request_id)
            if file_ext == '.pdf':
                raw_data = extract_invoice_data(file_bytes)
            else:
                raw_data = extract_invoice_data_from_image(file_bytes, SUPPORTED_IMAGE_EXTENSIONS[file_ext])
            _remember_read(request, org, raw_data, supplier if supplier_id else None)
            finish_read(read, success=True)
            completed = True
            return redirect('ingredients:invoice-confirm')
        except ValueError as exc:
            messages.error(request, str(exc))
        except Exception:
            messages.error(request, 'Odczyt nie powiódł się. Spróbuj ponownie za chwilę. Nie odjęliśmy stron z limitu.')
        finally:
            if read and not completed:
                finish_read(read, success=False)
                request.session.pop('invoice_items', None)
    return render(request, 'ingredients/invoice_upload.html', _upload_context(org))


@login_required
@setup_required
def invoice_confirm(request):
    """Krok 2 — podgląd wyciągniętych cen, korekta dopasowań, zapis."""
    org = request.user.organization
    items = request.session.get('invoice_items')
    session_supplier_id = request.session.get('invoice_supplier_id')  # może być None — nie wykryto
    meta = request.session.get('invoice_meta', {})

    if not items:
        messages.error(request, 'Brak danych faktury. Wgraj plik ponownie.')
        return redirect('ingredients:invoice-upload')

    suppliers_all = Supplier.objects.filter(organization=org).order_by('name')
    ingredients_all = Ingredient.objects.filter(organization=org, is_active=True).order_by('name')

    if request.method == 'POST':
        supplier_choice = request.POST.get('supplier_choice')
        if supplier_choice == '__new__':
            supplier_name = (meta.get('supplier_name') or 'Nowy dostawca').strip()[:200]
            supplier = Supplier.objects.filter(organization=org, name__iexact=supplier_name).first()
            if not supplier:
                supplier = Supplier.objects.create(organization=org, name=supplier_name)
        else:
            supplier = get_object_or_404(Supplier, pk=supplier_choice, organization=org)

        source_note = f"Faktura {meta.get('invoice_number') or ''} {meta.get('invoice_date') or ''} ({supplier.name})".strip()
        saved_count = 0
        skipped_count = 0

        for i, item in enumerate(items):
            if not request.POST.get(f'save_{i}'):
                skipped_count += 1
                continue

            ingredient_id = request.POST.get(f'ingredient_id_{i}')
            if not ingredient_id:
                skipped_count += 1
                continue

            price_str = request.POST.get(f'price_{i}', item['price'])
            unit = request.POST.get(f'unit_{i}', item['unit'])
            package_size_str = request.POST.get(f'package_size_{i}', '')
            is_netto = request.POST.get(f'is_netto_{i}') == '1'

            try:
                price = Decimal(str(price_str).replace(',', '.'))
                if not price.is_finite() or price < 0:
                    raise ValueError('Niepoprawna cena')
                package_size = Decimal(str(package_size_str).replace(',', '.')) if package_size_str else None

                if package_size is not None and (not package_size.is_finite() or package_size <= 0):
                    raise ValueError('Niepoprawne opakowanie')
                if unit not in {u for u, _ in UNIT_CHOICES}:
                    raise ValueError('Niepoprawna jednostka')

                if ingredient_id == '__new__':
                    # Świeża organizacja startuje z pustą listą składników —
                    # bez tego OCR nie miałby do czego dopasować pierwszą fakturę.
                    name = item['name'].strip()[:200]
                    ingredient = Ingredient.objects.filter(organization=org, name__iexact=name).first()
                    if not ingredient:
                        valid_units = {u for u, _ in UNIT_CHOICES}
                        ingredient = Ingredient.objects.create(
                            organization=org,
                            name=name,
                            base_unit=unit if unit in valid_units else 'kg',
                        )
                else:
                    # organization=org w lookupie — tenant isolation na wpisywanym ID
                    ingredient = Ingredient.objects.get(pk=int(ingredient_id), organization=org)

                new_price = SupplierPrice(
                    ingredient=ingredient,
                    supplier=supplier,
                    price=price,
                    unit=unit,
                    package_size=package_size,
                    is_netto=is_netto,
                    source_note=source_note,
                )
                new_price.clean()  # niezgodna jednostka → pominięcie zamiast cichej, błędnej ceny
                new_price.save()
                saved_count += 1
            except Exception:
                skipped_count += 1
                continue

        del request.session['invoice_items']
        request.session.pop('invoice_supplier_id', None)
        request.session.pop('invoice_meta', None)

        messages.success(request, f'Zapisano {saved_count} cen z faktury. Pominięto: {skipped_count}.')
        return redirect('ingredients:supplier-list')

    context = {
        'session_supplier_id': session_supplier_id,
        'suppliers_all': suppliers_all,
        'items': items,
        'meta': meta,
        'ingredients_all': ingredients_all,
        'units': ['kg', 'g', 'l', 'ml', 'szt', 'opak'],
    }
    return render(request, 'ingredients/invoice_confirm.html', context)
