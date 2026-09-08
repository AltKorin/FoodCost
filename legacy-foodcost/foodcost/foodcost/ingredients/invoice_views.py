"""
Widoki do obsługi faktur PDF — OCR + potwierdzenie cen.
Dodaj do ingredients/views.py lub importuj z urls.py.
"""
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from .models import Ingredient, Supplier, SupplierPrice
from .ocr_service import (
    extract_invoice_data, extract_invoice_data_from_image,
    normalize_items, fuzzy_match_ingredients, SUPPORTED_IMAGE_EXTENSIONS,
)


@login_required
def invoice_upload(request):
    """Krok 1 — wgranie PDF faktury lub zdjęcia i wybór dostawcy."""
    suppliers = Supplier.objects.filter(is_active=True)

    if request.method == 'POST':
        supplier_id = request.POST.get('supplier_id')
        upload_file = request.FILES.get('invoice_file')

        if not supplier_id:
            messages.error(request, 'Wybierz dostawcę.')
            return render(request, 'ingredients/invoice_upload.html', {'suppliers': suppliers})

        if not upload_file:
            messages.error(request, 'Wybierz plik faktury lub zdjęcie.')
            return render(request, 'ingredients/invoice_upload.html', {'suppliers': suppliers})

        if upload_file.size > 20 * 1024 * 1024:  # 20MB limit
            messages.error(request, 'Plik jest za duży (max 20MB).')
            return render(request, 'ingredients/invoice_upload.html', {'suppliers': suppliers})

        import os
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
                media_type = SUPPORTED_IMAGE_EXTENSIONS[file_ext]
                raw_data = extract_invoice_data_from_image(file_bytes, media_type)
            items = normalize_items(raw_data.get('items', []))

            if not items:
                messages.error(request, 'Nie znaleziono pozycji w fakturze. Sprawdź czy plik jest czytelny.')
                return render(request, 'ingredients/invoice_upload.html', {'suppliers': suppliers})

            # Dopasuj do składników w bazie
            ingredients_qs = Ingredient.objects.filter(is_active=True)
            items = fuzzy_match_ingredients(items, ingredients_qs)

            # Zapisz w sesji do potwierdzenia
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
            request.session['invoice_supplier_id'] = int(supplier_id)
            request.session['invoice_meta'] = {
                'supplier_name': raw_data.get('supplier_name'),
                'invoice_number': raw_data.get('invoice_number'),
                'invoice_date': raw_data.get('invoice_date'),
            }

            return redirect('invoice_confirm')

        except ImportError as e:
            messages.error(request, f'Brak wymaganej biblioteki: {e}')
        except ValueError as e:
            messages.error(request, f'Błąd przetwarzania: {e}')
        except Exception as e:
            messages.error(request, f'Nieoczekiwany błąd: {e}')

    return render(request, 'ingredients/invoice_upload.html', {'suppliers': suppliers})


@login_required
def invoice_confirm(request):
    """Krok 2 — podgląd wyciągniętych cen, korekta dopasowań, zapis."""
    items = request.session.get('invoice_items')
    supplier_id = request.session.get('invoice_supplier_id')
    meta = request.session.get('invoice_meta', {})

    if not items or not supplier_id:
        messages.error(request, 'Brak danych faktury. Wgraj plik ponownie.')
        return redirect('invoice_upload')

    supplier = get_object_or_404(Supplier, pk=supplier_id)
    ingredients_all = Ingredient.objects.filter(is_active=True).order_by('name')

    if request.method == 'POST':
        source_note = f"Faktura {meta.get('invoice_number') or ''} {meta.get('invoice_date') or ''} ({supplier.name})".strip()
        saved_count = 0
        skipped_count = 0

        for i, item in enumerate(items):
            # Sprawdź czy wiersz jest zaznaczony do zapisania
            if not request.POST.get(f'save_{i}'):
                skipped_count += 1
                continue

            # Pobierz wybrany składnik (może być zmieniony ręcznie)
            ingredient_id = request.POST.get(f'ingredient_id_{i}')
            if not ingredient_id:
                skipped_count += 1
                continue

            price_str = request.POST.get(f'price_{i}', item['price_per_unit'])
            unit = request.POST.get(f'unit_{i}', item['unit'])
            package_size_str = request.POST.get(f'package_size_{i}', '')
            is_netto = request.POST.get(f'is_netto_{i}') == '1'

            try:
                from decimal import Decimal
                price = Decimal(str(price_str).replace(',', '.'))
                package_size = Decimal(str(package_size_str).replace(',', '.')) if package_size_str else None

                SupplierPrice.objects.create(
                    ingredient_id=int(ingredient_id),
                    supplier=supplier,
                    price=price,
                    unit=unit,
                    package_size=package_size,
                    is_current=True,
                    is_netto=is_netto,
                    source_note=source_note,
                )
                saved_count += 1
            except Exception:
                skipped_count += 1
                continue

        # Wyczyść sesję
        del request.session['invoice_items']
        del request.session['invoice_supplier_id']
        request.session.pop('invoice_meta', None)

        messages.success(
            request,
            f'Zapisano {saved_count} cen z faktury. Pominięto: {skipped_count}.'
        )
        return redirect('price_update', supplier_id=supplier_id)

    context = {
        'supplier': supplier,
        'items': items,
        'meta': meta,
        'ingredients_all': ingredients_all,
        'units': ['kg', 'g', 'l', 'ml', 'szt', 'opak'],
    }
    return render(request, 'ingredients/invoice_confirm.html', context)
