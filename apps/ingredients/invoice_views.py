"""Widoki OCR faktur — wgraj (PDF/zdjęcie) → potwierdź dopasowania → zapisz ceny.

Funkcja płatna (plan Pro) — każde wgranie faktury to koszt tokenów OpenAI Vision.
"""
import os
import re
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect

from apps.accounts.decorators import setup_required, pro_required
from .models import Ingredient, Supplier, SupplierPrice, UNIT_CHOICES
from .ocr_service import (
    extract_invoice_data, extract_invoice_data_from_image,
    normalize_items, fuzzy_match_ingredients, SUPPORTED_IMAGE_EXTENSIONS,
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


@login_required
@setup_required
@pro_required
def invoice_upload(request):
    """Krok 1 — wgranie PDF faktury lub zdjęcia i wybór dostawcy."""
    org = request.user.organization
    suppliers = Supplier.objects.filter(organization=org)

    if request.method == 'POST':
        supplier_id = request.POST.get('supplier_id')  # opcjonalny — puste = wykryj z faktury
        upload_file = request.FILES.get('invoice_file')

        if not upload_file:
            messages.error(request, 'Wybierz plik faktury lub zdjęcie.')
            return render(request, 'ingredients/invoice_upload.html', {'suppliers': suppliers})

        if upload_file.size > 20 * 1024 * 1024:  # 20MB limit
            messages.error(request, 'Plik jest za duży (max 20MB).')
            return render(request, 'ingredients/invoice_upload.html', {'suppliers': suppliers})

        file_ext = os.path.splitext(upload_file.name.lower())[1]
        is_pdf = file_ext == '.pdf'
        is_image = file_ext in SUPPORTED_IMAGE_EXTENSIONS

        if not is_pdf and not is_image:
            messages.error(request, 'Obsługiwane formaty: PDF, JPG, PNG, WEBP.')
            return render(request, 'ingredients/invoice_upload.html', {'suppliers': suppliers})

        try:
            file_bytes = upload_file.read()
            if is_pdf:
                raw_data = extract_invoice_data(file_bytes)
            else:
                raw_data = extract_invoice_data_from_image(file_bytes, SUPPORTED_IMAGE_EXTENSIONS[file_ext])
            items = normalize_items(raw_data.get('items', []))

            if not items:
                messages.error(request, 'Nie znaleziono pozycji w fakturze. Sprawdź czy plik jest czytelny.')
                return render(request, 'ingredients/invoice_upload.html', {'suppliers': suppliers})

            ingredients_qs = Ingredient.objects.filter(organization=org, is_active=True)
            items = fuzzy_match_ingredients(items, ingredients_qs)

            supplier_name = raw_data.get('supplier_name')
            if supplier_id:
                resolved_supplier_id = int(supplier_id)
            else:
                matched_supplier = _match_supplier(supplier_name, suppliers)
                resolved_supplier_id = matched_supplier.pk if matched_supplier else None

            request.session['invoice_items'] = [
                {
                    'name': i['name'],
                    'price': str(i['price']),
                    'price_per_unit': str(i['price_per_unit']),
                    'unit': i['unit'],
                    'package_size': str(i['package_size']) if i['package_size'] else None,
                    'vat': i['vat'],
                    'is_netto': i['is_netto'],
                    'matched_ingredient_id': i['matched_ingredient'].pk if i['matched_ingredient'] else None,
                    'matched_ingredient_name': i['matched_ingredient'].name if i['matched_ingredient'] else None,
                    'match_score': round(i['match_score'], 2),
                }
                for i in items
            ]
            request.session['invoice_supplier_id'] = resolved_supplier_id
            request.session['invoice_meta'] = {
                'supplier_name': supplier_name,
                'invoice_number': raw_data.get('invoice_number'),
                'invoice_date': raw_data.get('invoice_date'),
            }

            return redirect('ingredients:invoice-confirm')

        except ImportError as e:
            messages.error(request, f'Brak wymaganej biblioteki: {e}')
        except ValueError as e:
            messages.error(request, f'Błąd przetwarzania: {e}')
        except Exception as e:
            messages.error(request, f'Nieoczekiwany błąd: {e}')

    return render(request, 'ingredients/invoice_upload.html', {'suppliers': suppliers})


@login_required
@setup_required
@pro_required
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

            price_str = request.POST.get(f'price_{i}', item['price_per_unit'])
            unit = request.POST.get(f'unit_{i}', item['unit'])
            package_size_str = request.POST.get(f'package_size_{i}', '')
            is_netto = request.POST.get(f'is_netto_{i}') == '1'

            try:
                price = Decimal(str(price_str).replace(',', '.'))
                package_size = Decimal(str(package_size_str).replace(',', '.')) if package_size_str else None

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

                SupplierPrice.objects.create(
                    ingredient=ingredient,
                    supplier=supplier,
                    price=price,
                    unit=unit,
                    package_size=package_size,
                    is_netto=is_netto,
                    source_note=source_note,
                )
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
