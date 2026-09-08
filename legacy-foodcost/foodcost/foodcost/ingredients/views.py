from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin

from .models import Ingredient, Supplier, SupplierPrice, Category
from recipes.models import Recipe, RecipeIngredient


@login_required
def dashboard(request):
    """Strona główna — przegląd FC i alerty."""
    recipes = Recipe.objects.filter(is_active=True).prefetch_related(
        'ingredients__ingredient__supplier_prices'
    )

    stats = {
        'recipes_total': recipes.count(),
        'recipes_no_price': 0,
        'recipes_over_fc': 0,
        'ingredients_no_price': Ingredient.objects.filter(
            is_active=True
        ).exclude(
            supplier_prices__is_current=True
        ).count(),
    }

    recipes_with_fc = []
    for recipe in recipes:
        fc = recipe.food_cost_percentage
        if fc is None:
            stats['recipes_no_price'] += 1
        elif fc > 38:
            stats['recipes_over_fc'] += 1
        recipes_with_fc.append({
            'recipe': recipe,
            'cost_per_portion': recipe.cost_per_portion,
            'fc_percentage': fc,
            'status': recipe.get_fc_status(),
        })

    # Posortuj — najpierw problematyczne
    status_order = {'danger': 0, 'warning': 1, 'unknown': 2, 'ok': 3}
    recipes_with_fc.sort(key=lambda x: status_order.get(x['status'], 4))

    context = {
        'stats': stats,
        'recipes_with_fc': recipes_with_fc[:20],
    }
    return render(request, 'dashboard.html', context)


@login_required
def price_update(request, supplier_id):
    """Panel szybkiej aktualizacji cen — główny widok dla Michała."""
    supplier = get_object_or_404(Supplier, pk=supplier_id, is_active=True)
    ingredients = Ingredient.objects.filter(is_active=True).order_by(
        'category__order', 'name'
    ).select_related('category')

    # Zbierz aktualne ceny tego dostawcy
    current_prices = {
        sp.ingredient_id: sp
        for sp in SupplierPrice.objects.filter(
            supplier=supplier, is_current=True
        ).select_related('ingredient')
    }

    if request.method == 'POST':
        updated_count = 0
        errors = []

        for ingredient in ingredients:
            price_key = f'price_{ingredient.pk}'
            unit_key = f'unit_{ingredient.pk}'
            note_key = f'note_{ingredient.pk}'

            price_str = request.POST.get(price_key, '').strip()
            unit = request.POST.get(unit_key, ingredient.base_unit)
            note = request.POST.get(note_key, '').strip()

            if not price_str:
                continue  # Puste pole — pomijamy

            try:
                price = float(price_str.replace(',', '.'))
                if price <= 0:
                    continue

                current = current_prices.get(ingredient.pk)

                # Aktualizuj tylko jeśli cena się zmieniła
                if current and float(current.price) == price and current.unit == unit:
                    continue

                SupplierPrice.objects.create(
                    ingredient=ingredient,
                    supplier=supplier,
                    price=price,
                    unit=unit,
                    is_current=True,
                    source_note=note or f'Aktualizacja {timezone.now().strftime("%d.%m.%Y")}',
                )
                updated_count += 1

            except (ValueError, TypeError):
                errors.append(f'Nieprawidłowa cena dla: {ingredient.name}')

        if errors:
            for err in errors:
                messages.error(request, err)

        if updated_count:
            messages.success(
                request,
                f'Zaktualizowano {updated_count} cen dla dostawcy {supplier.name}.'
            )
        else:
            messages.info(request, 'Brak zmian do zapisania.')

        return redirect('price_update', supplier_id=supplier_id)

    # Przygotuj dane do szablonu
    rows = []
    for ingredient in ingredients:
        current = current_prices.get(ingredient.pk)
        rows.append({
            'ingredient': ingredient,
            'current_price': current,
        })

    context = {
        'supplier': supplier,
        'rows': rows,
    }
    return render(request, 'ingredients/price_update.html', context)


class IngredientListView(LoginRequiredMixin, ListView):
    model = Ingredient
    template_name = 'ingredients/ingredient_list.html'
    context_object_name = 'ingredients'

    def get_queryset(self):
        qs = Ingredient.objects.filter(is_active=True).select_related('category')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(name__icontains=q)
        cat = self.request.GET.get('category')
        if cat:
            qs = qs.filter(category_id=cat)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['categories'] = Category.objects.all()
        ctx['current_prices'] = {
            sp.ingredient_id: sp
            for sp in SupplierPrice.objects.filter(is_current=True).select_related('supplier')
        }
        # Użycie składnika w przepisach
        ctx['usage_counts'] = {
            i['ingredient_id']: i['count']
            for i in RecipeIngredient.objects.values('ingredient_id')
            .annotate(count=Count('id'))
        }
        return ctx


class SupplierListView(LoginRequiredMixin, ListView):
    model = Supplier
    template_name = 'ingredients/supplier_list.html'
    context_object_name = 'suppliers'

    def get_queryset(self):
        return Supplier.objects.filter(is_active=True).annotate(
            price_count=Count('prices', filter=Q(prices__is_current=True))
        )


@login_required
def ingredient_edit(request, pk=None):
    ingredient = None
    if pk:
        ingredient = get_object_or_404(Ingredient, pk=pk)

    categories = Category.objects.all()
    units = [('kg', 'kg'), ('g', 'g'), ('l', 'l'), ('ml', 'ml'), ('szt', 'szt'), ('opak', 'opak')]

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Nazwa składnika jest wymagana.')
            return render(request, 'ingredients/ingredient_edit.html', {
                'ingredient': ingredient, 'categories': categories, 'units': units
            })

        data = {
            'name': name,
            'category_id': request.POST.get('category') or None,
            'base_unit': request.POST.get('base_unit', 'kg'),
            'notes': request.POST.get('notes', ''),
            'is_active': True,
        }

        if ingredient:
            for k, v in data.items():
                setattr(ingredient, k, v)
            ingredient.save()
            messages.success(request, f'Składnik "{ingredient.name}" zaktualizowany.')
        else:
            ingredient = Ingredient.objects.create(**data)
            messages.success(request, f'Składnik "{ingredient.name}" dodany.')

        return redirect('ingredient_list')

    return render(request, 'ingredients/ingredient_edit.html', {
        'ingredient': ingredient,
        'categories': categories,
        'units': units,
    })


@login_required
def ingredient_delete(request, pk):
    ingredient = get_object_or_404(Ingredient, pk=pk)
    if request.method == 'POST':
        # Miękkie usuwanie — zachowujemy historię cen
        ingredient.is_active = False
        ingredient.save()
        messages.success(request, f'Składnik "{ingredient.name}" usunięty.')
        return redirect('ingredient_list')
    return render(request, 'ingredients/ingredient_confirm_delete.html', {'ingredient': ingredient})


@login_required
def supplier_edit(request, pk=None):
    supplier = None
    if pk:
        supplier = get_object_or_404(Supplier, pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Nazwa dostawcy jest wymagana.')
            return render(request, 'ingredients/supplier_edit.html', {'supplier': supplier})

        data = {
            'name': name,
            'contact_name': request.POST.get('contact_name', ''),
            'phone': request.POST.get('phone', ''),
            'email': request.POST.get('email', ''),
            'delivery_days': request.POST.get('delivery_days', ''),
            'notes': request.POST.get('notes', ''),
            'is_active': True,
        }

        if supplier:
            for k, v in data.items():
                setattr(supplier, k, v)
            supplier.save()
            messages.success(request, f'Dostawca "{supplier.name}" zaktualizowany.')
        else:
            supplier = Supplier.objects.create(**data)
            messages.success(request, f'Dostawca "{supplier.name}" dodany.')

        return redirect('supplier_list')

    return render(request, 'ingredients/supplier_edit.html', {'supplier': supplier})


@login_required
def supplier_delete(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        supplier.is_active = False
        supplier.save()
        messages.success(request, f'Dostawca "{supplier.name}" usunięty.')
        return redirect('supplier_list')
    return render(request, 'ingredients/supplier_confirm_delete.html', {'supplier': supplier})
