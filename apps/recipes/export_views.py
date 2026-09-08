"""Eksport Menu do Word — dokument do pokazania klientowi/właścicielowi."""
import re

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from apps.accounts.decorators import setup_required
from .models import Menu

FC_STATUS_LABELS = {
    'ok': 'OK',
    'warning': 'Blisko limitu',
    'danger': 'Przekroczony',
    'unknown': 'Brak danych',
}


@login_required
@setup_required
def menu_export_word(request, pk):
    from docx import Document
    from docx.shared import Pt

    org = request.user.organization
    menu = get_object_or_404(Menu.objects.prefetch_related('items__recipe'), pk=pk, organization=org)

    doc = Document()
    doc.add_heading(menu.name, level=1)

    if menu.package_price_per_person:
        doc.add_paragraph(f'Cena pakietowa: {menu.package_price_per_person} PLN / osoba')
    doc.add_paragraph(f'Docelowy food cost: {menu.target_fc_pct}%')
    if not menu.is_cost_complete:
        p = doc.add_paragraph('Uwaga: nie wszystkie dania mają jeszcze policzony koszt — suma jest zaniżona.')
        p.runs[0].italic = True

    table = doc.add_table(rows=1, cols=4)
    table.style = 'Light Grid Accent 1'
    hdr = table.rows[0].cells
    hdr[0].text = 'Danie'
    hdr[1].text = 'Porcji / gościa'
    hdr[2].text = 'Koszt / porcję'
    hdr[3].text = 'Koszt razem'

    for item in menu.items.all():
        row = table.add_row().cells
        row[0].text = item.recipe.name
        row[1].text = str(item.quantity)
        row[2].text = f'{item.recipe.cost_per_portion} PLN' if item.recipe.has_cost_data else '—'
        row[3].text = f'{item.get_cost()} PLN'

    doc.add_paragraph()
    doc.add_paragraph(f'Koszt razem / osoba: {menu.total_cost_per_person} PLN').runs[0].bold = True
    if menu.food_cost_pct is not None:
        doc.add_paragraph(f'Food cost: {menu.food_cost_pct}% ({FC_STATUS_LABELS[menu.fc_status]})')

    for style_name in ('Normal',):
        doc.styles[style_name].font.size = Pt(11)

    safe_name = re.sub(r'[^\w\-]+', '_', menu.name).strip('_') or 'menu'
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    response['Content-Disposition'] = f'attachment; filename="{safe_name}.docx"'
    doc.save(response)
    return response
