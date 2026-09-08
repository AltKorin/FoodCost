"""
Widoki do importu cenników z plików Excel/CSV.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from .models import Ingredient, Supplier, SupplierPrice
from .spreadsheet_service import read_file, auto_detect_columns, parse_rows
from .ocr_service import fuzzy_match_ingredients


@login_required
def spreadsheet_upload(request):
    """Krok 1 — wgranie pliku Excel/CSV i wybór dostawcy."""
    suppliers = Supplier.objects.filter(is_active=True)

    if request.method == 'POST':
        supplier_id = request.POST.get('supplier_id')
        upload_file = request.FILES.get('price_file')

        if not supplier_id:
            messages.error(request, 'Wybierz dostawcę.')
            return render(request, 'ingredients/spreadsheet_upload.html', {'suppliers': suppliers})

        if not upload_file:
            messages.error(request, 'Wybierz plik.')
            return render(request, 'ingredients/spreadsheet_upload.html', {'suppliers': suppliers})

        if upload_file.size > 10 * 1024 * 1024:
            messages.error(request, 'Plik jest za duży (max 10MB).')
            return render(request, 'ingredients/spreadsheet_upload.html', {'suppliers': suppliers})

        try:
            file_bytes = upload_file.read()
            headers, rows = read_file(file_bytes, upload_file.name)

            if not headers:
                messages.error(request, 'Nie znaleziono nagłówków w pliku.')
                return render(request, 'ingredients/spreadsheet_upload.html', {'suppliers': suppliers})

            # Auto-wykryj mapowanie kolumn
            mapping = auto_detect_columns(headers)

            # Zapisz w sesji
            request.session['spreadsheet_headers'] = headers
            request.session['spreadsheet_rows'] = [
                [str(cell) for cell in row] for row in rows[:500]
            ]
            request.session['spreadsheet_supplier_id'] = int(supplier_id)
            request.session['spreadsheet_mapping'] = mapping
            request.session['spreadsheet_filename'] = upload_file.name

            return redirect('spreadsheet_map')

        except (ImportError, ValueError) as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Błąd podczas wczytywania pliku: {e}')

    return render(request, 'ingredients/spreadsheet_upload.html', {'suppliers': suppliers})


@login_required
def spreadsheet_map(request):
    """Krok 2 — mapowanie kolumn jeśli auto-wykrycie było niepewne."""
    headers = request.session.get('spreadsheet_headers')
    rows = request.session.get('spreadsheet_rows')
    supplier_id = request.session.get('spreadsheet_supplier_id')
    mapping = request.session.get('spreadsheet_mapping', {})
    filename = request.session.get('spreadsheet_filename', '')

    if not headers or not supplier_id:
        messages.error(request, 'Brak danych — wgraj plik ponownie.')
        return redirect('spreadsheet_upload')

    supplier = get_object_or_404(Supplier, pk=supplier_id)

    if request.method == 'POST':
        # Pobierz mapowanie od użytkownika
        new_mapping = {}
        for field in ['name', 'price', 'unit', 'package_size', 'vat']:
            val = request.POST.get(f'col_{field}')
            if val and val != '-1':
                try:
                    new_mapping[field] = int(val)
                except ValueError:
                    pass

        if 'name' not in new_mapping or 'price' not in new_mapping:
            messages.error(request, 'Musisz wybrać co najmniej kolumny: Nazwa i Cena.')
            return render(request, 'ingredients/spreadsheet_map.html', {
                'headers': headers,
                'preview_rows': rows[:5],
                'mapping': new_mapping,
                'supplier': supplier,
                'filename': filename,
            })

        # Parsuj dane z nowym mapowaniem
        parsed = parse_rows(rows, new_mapping)

        if not parsed:
            messages.error(request, 'Nie znaleziono żadnych pozycji — sprawdź mapowanie kolumn.')
            return render(request, 'ingredients/spreadsheet_map.html', {
                'headers': headers,
                'preview_rows': rows[:5],
                'mapping': new_mapping,
                'supplier': supplier,
                'filename': filename,
            })

        # Fuzzy match do składników w bazie
        ingredients_qs = Ingredient.objects.filter(is_active=True)
        parsed = fuzzy_match_ingredients(parsed, ingredients_qs)

        # Zapisz w sesji
        request.session['spreadsheet_parsed'] = [
            {
                'name': i['name'],
                'price': str(i['price']),
                'unit': i['unit'],
                'package_size': str(i['package_size']) if i['package_size'] else None,
                'vat': i['vat'],
                'is_netto': i['is_netto'],
                'matched_ingredient_id': i['matched_ingredient'].pk if i['matched_ingredient'] else None,
                'matched_ingredient_name': i['matched_ingredient'].name if i['matched_ingredient'] else None,
                'match_score': round(i['match_score'], 2),
            }
            for i in parsed
        ]

        return redirect('spreadsheet_confirm')

    # Podgląd pierwszych 5 wierszy
    preview_rows = rows[:5]

    context = {
        'headers': headers,
        'preview_rows': preview_rows,
        'mapping': mapping,
        'supplier': supplier,
        'filename': filename,
        'fields': [
            ('name', 'Nazwa produktu *'),
            ('price', 'Cena *'),
            ('unit', 'Jednostka'),
            ('package_size', 'Ilość w opakowaniu'),
            ('vat', 'VAT %'),
        ],
    }
    return render(request, 'ingredients/spreadsheet_map.html', context)


@login_required
def spreadsheet_confirm(request):
    """Krok 3 — podgląd, korekta dopasowań, zapis."""
    items = request.session.get('spreadsheet_parsed')
    supplier_id = request.session.get('spreadsheet_supplier_id')
    filename = request.session.get('spreadsheet_filename', '')

    if not items or not supplier_id:
        messages.error(request, 'Brak danych — wgraj plik ponownie.')
        return redirect('spreadsheet_upload')

    supplier = get_object_or_404(Supplier, pk=supplier_id)
    ingredients_all = Ingredient.objects.filter(is_active=True).order_by('name')

    if request.method == 'POST':
        source_note = f'Import: {filename} ({timezone.now().strftime("%d.%m.%Y")})'
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
        for key in ['spreadsheet_parsed', 'spreadsheet_supplier_id',
                    'spreadsheet_headers', 'spreadsheet_rows',
                    'spreadsheet_mapping', 'spreadsheet_filename']:
            request.session.pop(key, None)

        messages.success(request, f'Zapisano {saved_count} cen. Pominięto: {skipped_count}.')
        return redirect('price_update', supplier_id=supplier_id)

    context = {
        'supplier': supplier,
        'items': items,
        'filename': filename,
        'ingredients_all': ingredients_all,
        'units': ['kg', 'g', 'l', 'ml', 'szt', 'opak'],
    }
    return render(request, 'ingredients/spreadsheet_confirm.html', context)
