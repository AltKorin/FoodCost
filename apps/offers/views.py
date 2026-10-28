from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from apps.accounts.decorators import setup_required
from .forms import OfferForm, LineFormSet
from .models import Offer


def queryset(request):
    return Offer.objects.filter(organization=request.user.organization).prefetch_related('lines')


@login_required
@setup_required
def offer_list(request):
    q = request.GET.get('q', '').strip()
    offers = queryset(request)
    if q:
        offers = offers.filter(Q(title__icontains=q) | Q(client_name__icontains=q))
    return render(request, 'offers/list.html', {'page_obj': Paginator(offers, 25).get_page(request.GET.get('page')), 'q': q})


@login_required
@setup_required
def offer_detail(request, pk):
    return render(request, 'offers/detail.html', {'offer': get_object_or_404(queryset(request), pk=pk)})


@login_required
@setup_required
def offer_print(request, pk):
    return render(request, 'offers/print.html', {'offer': get_object_or_404(queryset(request), pk=pk)})


def snapshot_line(line, previous_menu_id, refresh):
    if line.menu_id and (not line.pk or previous_menu_id != line.menu_id or refresh):
        menu = line.menu
        line.description = line.description or menu.name
        line.details = '\n'.join(item.recipe.name for item in menu.items.select_related('recipe').all())
        line.cost_per_unit = menu.total_cost_per_person
        line.cost_complete = menu.is_cost_complete  # ta sama definicja co w Menu
    elif not line.menu_id:
        line.cost_per_unit = None
        line.cost_complete = False


@login_required
@setup_required
def offer_edit(request, pk=None):
    if request.user.role == 'viewer':
        return HttpResponseForbidden('Konto z rolą Podgląd nie może edytować ofert.')
    offer = get_object_or_404(queryset(request), pk=pk) if pk else Offer(organization=request.user.organization, seller_name=request.user.organization.name, created_by=request.user)
    previous_menus = {line.pk: line.menu_id for line in offer.lines.all()} if pk else {}
    form = OfferForm(request.POST or None, instance=offer)
    lines = LineFormSet(request.POST or None, instance=offer, prefix='lines', form_kwargs={'organization': request.user.organization})
    if request.method == 'POST':
        valid_form = form.is_valid()
        valid_lines = lines.is_valid()
        if valid_form and valid_lines:
            with transaction.atomic():
                if pk:
                    current = Offer.objects.select_for_update().get(pk=pk, organization=request.user.organization)
                    if form.cleaned_data['revision'] != current.revision:
                        form.add_error(None, 'Oferta została zmieniona przez inną osobę. Otwórz ją ponownie, aby zobaczyć aktualne dane.')
                    else:
                        offer.revision = current.revision + 1
                if not form.errors:
                    offer = form.save()
                    changed = lines.save(commit=False)
                    for deleted in lines.deleted_objects:
                        deleted.delete()
                    for line in changed:
                        line.offer = offer
                        line_form = next(f for f in lines.forms if f.instance is line)
                        snapshot_line(line, previous_menus.get(line.pk), line_form.cleaned_data.get('refresh_menu'))
                        line.save()
                    messages.success(request, 'Oferta zapisana.')
                    return redirect('offers:detail', pk=offer.pk)
    return render(request, 'offers/form.html', {'form': form, 'lines': lines, 'offer': offer, 'editing': bool(pk)})
