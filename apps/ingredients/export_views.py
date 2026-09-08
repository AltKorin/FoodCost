"""Eksport listy składników i cen dostawców do CSV / Excel."""
import csv
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

from apps.accounts.decorators import setup_required
from .models import Ingredient

HEADERS = [
    'Kategoria', 'Składnik', 'Jedn. bazowa', 'Dostawca',
    'Cena', 'Jedn. faktury', 'Cena/jedn. bazowa', 'Netto/Brutto', 'Ważna od',
]


def _price_rows(org):
    """Jeden wiersz na (składnik, aktualna cena dostawcy) — składnik bez
    żadnej ceny i tak trafia do eksportu, z pustymi kolumnami cenowymi."""
    ingredients = (
        Ingredient.objects.filter(organization=org, is_active=True)
        .select_related('category')
        .prefetch_related('prices__supplier')
        .order_by('name')
    )
    rows = []
    for ing in ingredients:
        category_name = ing.category.name if ing.category else ''
        prices = [p for p in ing.prices.all() if p.is_current]
        if not prices:
            rows.append([category_name, ing.name, ing.get_base_unit_display(), '', '', '', '', '', ''])
            continue
        for p in prices:
            rows.append([
                category_name,
                ing.name,
                ing.get_base_unit_display(),
                p.supplier.name,
                p.price,
                p.get_unit_display(),
                p.price_per_base_unit,
                'netto' if p.is_netto else 'brutto',
                p.valid_from.strftime('%Y-%m-%d'),
            ])
    return rows


@login_required
@setup_required
def export_ingredients_csv(request):
    org = request.user.organization
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="skladniki_{org.slug}.csv"'
    writer = csv.writer(response, delimiter=';')
    writer.writerow(HEADERS)
    writer.writerows(_price_rows(org))
    return response


@login_required
@setup_required
def export_ingredients_excel(request):
    from openpyxl import Workbook

    org = request.user.organization
    wb = Workbook()
    ws = wb.active
    ws.title = 'Składniki'
    ws.append(HEADERS)
    for row in _price_rows(org):
        ws.append([float(v) if isinstance(v, Decimal) else v for v in row])

    for col in ws.columns:
        width = max((len(str(c.value)) for c in col if c.value is not None), default=8)
        ws.column_dimensions[col[0].column_letter].width = min(width + 2, 40)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="skladniki_{org.slug}.xlsx"'
    wb.save(response)
    return response
