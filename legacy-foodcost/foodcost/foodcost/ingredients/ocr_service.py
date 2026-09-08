"""
Serwis OCR faktur — PDF lub obraz → OpenAI Vision → lista produktów z cenami.
"""
import base64
import json
import re
from decimal import Decimal, InvalidOperation

from django.conf import settings


# Obsługiwane formaty obrazów (rozszerzenie → MIME type)
SUPPORTED_IMAGE_EXTENSIONS = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.webp': 'image/webp',
}


EXTRACTION_PROMPT = """Jesteś asystentem do analizy faktur hurtowych dla gastronomii.
Przeanalizuj tę fakturę i wyciągnij WSZYSTKIE pozycje produktów.

Dla każdej pozycji zwróć:
- name: dokładna nazwa produktu z faktury
- quantity: ilość w opakowaniu (np. 5 dla kartonu 5kg) — null jeśli cena za jednostkę
- unit: jednostka (kg, g, l, ml, szt, opak)
- price: cena (liczba)
- price_type: "za_opakowanie" lub "za_jednostke"
- vat: stawka VAT w % (np. 5, 8, 23) — null jeśli brak

Odpowiedz TYLKO w formacie JSON, bez żadnego tekstu przed ani po:
{
  "supplier_name": "nazwa dostawcy z faktury lub null",
  "invoice_number": "numer faktury lub null",
  "invoice_date": "data w formacie YYYY-MM-DD lub null",
  "items": [
    {
      "name": "Filet z łososia 2-3kg",
      "quantity": 5,
      "unit": "kg",
      "price": 245.00,
      "price_type": "za_opakowanie",
      "vat": 5
    }
  ]
}

Jeśli nie możesz odczytać jakiejś wartości — wpisz null.
Nie pomijaj żadnych pozycji."""


def pdf_to_images_base64(pdf_bytes, max_pages=10):
    """Konwertuje PDF do listy base64 obrazów (jedna strona = jeden obraz)."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError("PyMuPDF nie jest zainstalowany. Uruchom: pip install PyMuPDF")

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []

    for page_num in range(min(len(doc), max_pages)):
        page = doc[page_num]
        # Render w wyższej rozdzielczości dla lepszego OCR
        mat = fitz.Matrix(2.0, 2.0)  # 2x zoom = ~144 DPI
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        img_b64 = base64.b64encode(img_bytes).decode('utf-8')
        images.append(img_b64)

    doc.close()
    return images


def _call_openai_vision(content):
    """Wysyła content do OpenAI Vision i zwraca sparsowane dane faktury."""
    from openai import OpenAI

    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError("Brak klucza OPENAI_API_KEY w ustawieniach.")

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": content}],
        max_tokens=2000,
        temperature=0,
    )

    raw_text = response.choices[0].message.content.strip()
    raw_text = re.sub(r'^```json\s*', '', raw_text)
    raw_text = re.sub(r'\s*```$', '', raw_text)

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Błąd parsowania odpowiedzi AI: {e}\nOdpowiedź: {raw_text[:500]}")


def extract_invoice_data(pdf_bytes):
    """Przyjmuje bytes PDFa, zwraca sparsowane dane faktury."""
    images = pdf_to_images_base64(pdf_bytes)
    if not images:
        raise ValueError("Nie udało się przetworzyć PDF — brak stron.")

    content = [{"type": "text", "text": EXTRACTION_PROMPT}]
    for img_b64 in images:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{img_b64}", "detail": "high"}
        })

    return _call_openai_vision(content)


def extract_invoice_data_from_image(image_bytes, media_type='image/jpeg'):
    """Przyjmuje bytes obrazu (JPG/PNG/WEBP), zwraca sparsowane dane faktury."""
    img_b64 = base64.b64encode(image_bytes).decode('utf-8')
    content = [
        {"type": "text", "text": EXTRACTION_PROMPT},
        {
            "type": "image_url",
            "image_url": {"url": f"data:{media_type};base64,{img_b64}", "detail": "high"}
        }
    ]
    return _call_openai_vision(content)


def normalize_items(items):
    """
    Normalizuje pozycje z faktury do formatu gotowego do wyświetlenia.
    Zwraca listę słowników z polami: name, price_per_unit, unit, raw_price, raw_quantity, vat
    """
    normalized = []
    for item in items:
        try:
            price = Decimal(str(item.get('price') or 0))
            quantity = item.get('quantity')
            unit = item.get('unit', 'szt') or 'szt'
            price_type = item.get('price_type', 'za_jednostke')
            vat = item.get('vat')

            if quantity and price_type == 'za_opakowanie':
                qty = Decimal(str(quantity))
                price_per_unit = (price / qty).quantize(Decimal('0.01'))
            else:
                price_per_unit = price
                quantity = None

            normalized.append({
                'name': item.get('name', '').strip(),
                'price': price,
                'price_per_unit': price_per_unit,
                'unit': unit,
                'package_size': Decimal(str(quantity)) if quantity else None,
                'vat': vat,
                'is_netto': True,  # Faktury hurtowe są zwykle netto
            })
        except (InvalidOperation, TypeError, ZeroDivisionError):
            continue

    return normalized


def fuzzy_match_ingredients(items, ingredients_qs):
    """
    Próbuje dopasować nazwy z faktury do składników w bazie.
    Zwraca listę items z dodanym polem 'matched_ingredient_id' (lub None).
    """
    # Prosta heurystyka — szukamy czy słowa z nazwy faktury zawierają się w nazwie składnika
    ingredient_map = {
        ing.name.lower(): ing
        for ing in ingredients_qs
    }

    for item in items:
        name_lower = item['name'].lower()
        matched = None
        best_score = 0

        for ing_name_lower, ing in ingredient_map.items():
            # Policz ile słów z nazwy faktury jest w nazwie składnika
            words_invoice = set(re.findall(r'\w{3,}', name_lower))
            words_db = set(re.findall(r'\w{3,}', ing_name_lower))
            if not words_invoice:
                continue
            common = words_invoice & words_db
            score = len(common) / len(words_invoice)
            if score > best_score and score >= 0.5:
                best_score = score
                matched = ing

        item['matched_ingredient'] = matched
        item['match_score'] = best_score

    return items
