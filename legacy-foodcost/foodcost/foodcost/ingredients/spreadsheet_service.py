"""
Import cenników dostawców z plików Excel (.xlsx, .xls) i CSV.
Strategia: wczytaj plik → spróbuj auto-wykryć kolumny → pokaż podgląd → użytkownik mapuje kolumny → zapisz.
"""
import csv
import io
from decimal import Decimal, InvalidOperation


# Słowa kluczowe do auto-wykrywania kolumn (małe litery)
COLUMN_HINTS = {
    'name': [
        'nazwa', 'name', 'produkt', 'product', 'towar', 'artykuł', 'article',
        'opis', 'description', 'pozycja', 'item'
    ],
    'price': [
        'cena', 'price', 'cena netto', 'netto', 'net', 'kwota', 'wartość',
        'cena jedn', 'cena/jedn', 'cena jednostkowa', 'unit price', 'cennik'
    ],
    'unit': [
        'jednostka', 'unit', 'jedn', 'jm', 'j.m.', 'uom', 'miary'
    ],
    'package_size': [
        'opakowanie', 'package', 'ilość w op', 'il. w op', 'op.', 'karton',
        'szt w op', 'zawartość', 'qty', 'ilość', 'gramatura'
    ],
    'vat': [
        'vat', 'podatek', 'stawka vat', 'tax', '%vat'
    ],
}


def read_file(file_bytes, filename):
    """
    Wczytuje plik Excel lub CSV i zwraca (headers, rows).
    headers: lista nazw kolumn
    rows: lista list z wartościami (stringi)
    """
    fname = filename.lower()

    if fname.endswith('.csv'):
        return _read_csv(file_bytes)
    elif fname.endswith('.xlsx') or fname.endswith('.xls'):
        return _read_excel(file_bytes, fname)
    else:
        raise ValueError(f'Nieobsługiwany format pliku: {filename}. Użyj .xlsx, .xls lub .csv')


def _read_csv(file_bytes):
    """Wczytuje CSV — próbuje auto-wykryć separator i kodowanie."""
    # Próbuj UTF-8, potem cp1250 (Windows polska)
    for encoding in ('utf-8-sig', 'cp1250', 'iso-8859-2', 'utf-8'):
        try:
            text = file_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError('Nie można odczytać pliku CSV — sprawdź kodowanie.')

    # Auto-wykryj separator
    sample = text[:2000]
    delimiter = ';'  # Domyślnie średnik (polskie Excele)
    if sample.count(',') > sample.count(';'):
        delimiter = ','

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)

    if not rows:
        raise ValueError('Plik CSV jest pusty.')

    # Znajdź wiersz z nagłówkami — szukamy pierwszego niepustego wiersza
    header_row_idx = 0
    for i, row in enumerate(rows):
        if any(cell.strip() for cell in row):
            header_row_idx = i
            break

    headers = [cell.strip() for cell in rows[header_row_idx]]
    data_rows = [
        [cell.strip() for cell in row]
        for row in rows[header_row_idx + 1:]
        if any(cell.strip() for cell in row)
    ]

    return headers, data_rows


def _read_excel(file_bytes, filename):
    """Wczytuje Excel przez openpyxl."""
    try:
        import openpyxl
    except ImportError:
        raise ImportError('openpyxl nie jest zainstalowany. Uruchom: pip install openpyxl')

    try:
        wb = openpyxl.load_workbook(
            io.BytesIO(file_bytes),
            read_only=True,
            data_only=True
        )
    except Exception as e:
        raise ValueError(f'Nie można otworzyć pliku Excel: {e}')

    ws = wb.active
    rows = []
    for row in ws.iter_rows(values_only=True):
        rows.append([str(cell).strip() if cell is not None else '' for cell in row])
    wb.close()

    if not rows:
        raise ValueError('Plik Excel jest pusty.')

    # Znajdź wiersz nagłówkowy
    header_row_idx = _find_header_row(rows)
    headers = rows[header_row_idx]
    data_rows = [
        row for row in rows[header_row_idx + 1:]
        if any(cell for cell in row)
    ]

    return headers, data_rows


def _find_header_row(rows, max_scan=10):
    """Szuka wiersza z nagłówkami w pierwszych max_scan wierszach."""
    best_idx = 0
    best_score = 0

    for i, row in enumerate(rows[:max_scan]):
        score = 0
        for cell in row:
            cell_lower = cell.lower()
            for hints in COLUMN_HINTS.values():
                if any(hint in cell_lower for hint in hints):
                    score += 1
        if score > best_score:
            best_score = score
            best_idx = i

    return best_idx


def auto_detect_columns(headers):
    """
    Próbuje automatycznie dopasować kolumny do pól.
    Zwraca słownik: {'name': idx, 'price': idx, 'unit': idx, ...} lub None jeśli nie znaleziono.
    """
    mapping = {}
    headers_lower = [h.lower() for h in headers]

    for field, hints in COLUMN_HINTS.items():
        for idx, header in enumerate(headers_lower):
            if any(hint in header for hint in hints):
                if field not in mapping:  # Weź pierwsze trafienie
                    mapping[field] = idx
                break

    return mapping


def parse_rows(rows, mapping, max_rows=500):
    """
    Przetwarza wiersze danych wg mapowania kolumn.
    Zwraca listę słowników z polami: name, price, unit, package_size, vat.
    """
    parsed = []

    for row in rows[:max_rows]:
        # Rozszerz wiersz jeśli za krótki
        row_extended = row + [''] * (max(mapping.values(), default=0) + 1 - len(row))

        name_idx = mapping.get('name')
        price_idx = mapping.get('price')

        if name_idx is None or price_idx is None:
            continue

        name = row_extended[name_idx].strip() if name_idx < len(row_extended) else ''
        price_raw = row_extended[price_idx].strip() if price_idx < len(row_extended) else ''

        if not name or not price_raw:
            continue

        # Parsuj cenę
        try:
            price_clean = price_raw.replace(' ', '').replace(',', '.').replace('zł', '').replace('PLN', '').strip()
            price = Decimal(price_clean)
            if price <= 0:
                continue
        except (InvalidOperation, ValueError):
            continue

        # Jednostka
        unit_idx = mapping.get('unit')
        unit = row_extended[unit_idx].strip() if unit_idx is not None and unit_idx < len(row_extended) else 'kg'
        unit = _normalize_unit(unit)

        # Rozmiar opakowania
        pkg_idx = mapping.get('package_size')
        package_size = None
        if pkg_idx is not None and pkg_idx < len(row_extended):
            pkg_raw = row_extended[pkg_idx].strip()
            try:
                pkg_clean = pkg_raw.replace(',', '.').replace(' ', '')
                pkg_val = Decimal(pkg_clean)
                if pkg_val > 0:
                    package_size = pkg_val
            except (InvalidOperation, ValueError):
                pass

        # VAT
        vat_idx = mapping.get('vat')
        vat = None
        if vat_idx is not None and vat_idx < len(row_extended):
            vat_raw = row_extended[vat_idx].strip().replace('%', '').replace(',', '.').strip()
            try:
                vat = int(float(vat_raw))
            except (ValueError, TypeError):
                pass

        parsed.append({
            'name': name,
            'price': price,
            'unit': unit,
            'package_size': package_size,
            'vat': vat,
            'is_netto': True,  # Domyślnie netto dla cenników hurtowych
        })

    return parsed


def _normalize_unit(unit_str):
    """Normalizuje jednostkę do obsługiwanego formatu."""
    u = unit_str.lower().strip().rstrip('.')
    mapping = {
        'kg': 'kg', 'kilogram': 'kg', 'kilo': 'kg',
        'g': 'g', 'gr': 'g', 'gram': 'g', 'gramy': 'g',
        'l': 'l', 'litr': 'l', 'liter': 'l', 'litry': 'l',
        'ml': 'ml', 'mililitr': 'ml',
        'szt': 'szt', 'sztuka': 'szt', 'sztuki': 'szt', 'pcs': 'szt', 'pc': 'szt',
        'opak': 'opak', 'opakowanie': 'opak', 'op': 'opak', 'karton': 'opak',
    }
    return mapping.get(u, 'szt')  # Domyślnie szt jeśli nieznana
