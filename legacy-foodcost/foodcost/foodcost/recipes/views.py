from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView

from .models import Recipe, RecipeIngredient, RecipeContext, MenuContext, MealType
from ingredients.models import Ingredient, SupplierPrice


class RecipeListView(LoginRequiredMixin, ListView):
    model = Recipe
    template_name = 'recipes/recipe_list.html'
    context_object_name = 'recipes'

    def get_queryset(self):
        qs = Recipe.objects.filter(is_active=True).prefetch_related(
            'ingredients__ingredient__supplier_prices',
            'contexts'
        )
        context_filter = self.request.GET.get('context')
        meal_filter = self.request.GET.get('meal_type')
        q = self.request.GET.get('q')

        if context_filter:
            qs = qs.filter(contexts__context=context_filter)
        if meal_filter:
            qs = qs.filter(meal_type=meal_filter)
        if q:
            qs = qs.filter(name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['contexts'] = MenuContext.choices
        ctx['meal_types'] = MealType.choices
        ctx['current_context'] = self.request.GET.get('context', '')
        ctx['current_meal'] = self.request.GET.get('meal_type', '')

        # Dodaj FC do każdego przepisu
        recipes_data = []
        for recipe in ctx['recipes']:
            recipes_data.append({
                'recipe': recipe,
                'cost_per_portion': recipe.cost_per_portion,
                'fc_percentage': recipe.food_cost_percentage,
                'status': recipe.get_fc_status(),
            })
        ctx['recipes_data'] = recipes_data
        return ctx


@login_required
def recipe_detail(request, pk):
    recipe = get_object_or_404(
        Recipe.objects.prefetch_related(
            'ingredients__ingredient__supplier_prices__supplier',
            'contexts'
        ),
        pk=pk
    )

    # Szczegółowy breakdown kosztów
    cost_breakdown = []
    total_cost = 0
    missing_prices = []

    for ri in recipe.ingredients.all():
        cost = ri.get_cost()
        if cost is not None:
            total_cost += cost
            cost_breakdown.append({
                'ri': ri,
                'cost': cost,
            })
        else:
            missing_prices.append(ri.ingredient.name)
            cost_breakdown.append({
                'ri': ri,
                'cost': None,
            })

    context = {
        'recipe': recipe,
        'cost_breakdown': cost_breakdown,
        'total_cost': total_cost,
        'missing_prices': missing_prices,
        'cost_per_portion': recipe.cost_per_portion,
        'fc_percentage': recipe.food_cost_percentage,
        'status': recipe.get_fc_status(),
    }
    return render(request, 'recipes/recipe_detail.html', context)


@login_required
def recipe_edit(request, pk=None):
    """Tworzenie i edycja przepisu z dynamicznym dodawaniem składników."""
    recipe = None
    if pk:
        recipe = get_object_or_404(Recipe, pk=pk)

    ingredients_all = Ingredient.objects.filter(is_active=True).select_related('category').order_by('name')
    contexts_all = RecipeContext.objects.all()

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Nazwa dania jest wymagana.')
            return redirect('recipe_edit')

        def _dec(val):
            """Konwertuje wartość z formularza na string z kropką (obsługa polskiego przecinka)."""
            if not val:
                return None
            return val.replace(',', '.')

        # Dane przepisu
        recipe_data = {
            'name': name,
            'description': request.POST.get('description', ''),
            'meal_type': request.POST.get('meal_type', 'main'),
            'yield_portions': _dec(request.POST.get('yield_portions', '1')) or 1,
            'selling_price': _dec(request.POST.get('selling_price')),
            'package_price_per_person': _dec(request.POST.get('package_price_per_person')),
            'notes': request.POST.get('notes', ''),
        }

        if recipe:
            for key, val in recipe_data.items():
                setattr(recipe, key, val)
            recipe.save()
            recipe.contexts.set(
                RecipeContext.objects.filter(
                    context__in=request.POST.getlist('contexts')
                )
            )
            # Usuń stare składniki i zapisz nowe
            recipe.ingredients.all().delete()
        else:
            recipe = Recipe.objects.create(**recipe_data)
            recipe.contexts.set(
                RecipeContext.objects.filter(
                    context__in=request.POST.getlist('contexts')
                )
            )

        # Składniki — przesłane jako lista
        ingredient_ids = request.POST.getlist('ingredient_id[]')
        quantities = request.POST.getlist('quantity[]')
        units = request.POST.getlist('unit[]')
        yield_factors = request.POST.getlist('yield_factor[]')
        optionals = request.POST.getlist('is_optional[]')
        ing_notes = request.POST.getlist('ing_notes[]')
        supplier_ids = request.POST.getlist('supplier_id[]')

        for i, ing_id in enumerate(ingredient_ids):
            if not ing_id:
                continue
            try:
                supplier_id = supplier_ids[i] if i < len(supplier_ids) else ''
                RecipeIngredient.objects.create(
                    recipe=recipe,
                    ingredient_id=int(ing_id),
                    preferred_supplier_id=int(supplier_id) if supplier_id else None,
                    quantity=float(quantities[i].replace(',', '.')),
                    unit=units[i],
                    yield_factor=float((yield_factors[i] or '1').replace(',', '.')),
                    is_optional=str(i) in optionals,
                    notes=ing_notes[i] if i < len(ing_notes) else '',
                )
            except (ValueError, IndexError, Ingredient.DoesNotExist):
                continue

        messages.success(request, f'Przepis "{recipe.name}" zapisany.')
        return redirect('recipe_detail', pk=recipe.pk)

    context = {
        'recipe': recipe,
        'ingredients_all': ingredients_all,
        'contexts_all': contexts_all,
        'meal_types': MealType.choices,
        'units': ['g', 'kg', 'ml', 'l', 'szt', 'opak'],
    }
    return render(request, 'recipes/recipe_edit.html', context)


@login_required
def ingredient_report(request):
    """Raport: które składniki powtarzają się w przepisach — strategia zakupów."""
    data = (
        Ingredient.objects
        .filter(is_active=True)
        .annotate(recipe_count=Count('used_in__recipe', distinct=True))
        .filter(recipe_count__gt=0)
        .order_by('-recipe_count')
        .select_related('category')
        .prefetch_related('supplier_prices__supplier')
    )

    context = {
        'ingredients': data,
        'title': 'Strategia zakupów — powtarzające się składniki',
    }
    return render(request, 'recipes/ingredient_report.html', context)


@login_required
def api_ingredient_price(request, ingredient_id):
    """API endpoint — wszystkie ceny składnika dla live preview w edytorze przepisu."""
    try:
        ingredient = Ingredient.objects.get(pk=ingredient_id, is_active=True)
        prices = ingredient.supplier_prices.filter(
            is_current=True
        ).select_related('supplier').order_by('price_per_base_unit')

        best = prices.first()
        prices_list = [
            {
                'supplier_id': p.supplier_id,
                'supplier': p.supplier.name,
                'price': float(p.price),
                'unit': p.unit,
                'price_per_base_unit': float(p.price_per_base_unit),
                'is_netto': p.is_netto,
                'is_best': p == best,
            }
            for p in prices
        ]

        return JsonResponse({
            'price_per_base_unit': float(best.price_per_base_unit) if best else None,
            'base_unit': ingredient.base_unit,
            'prices': prices_list,
        })
    except Ingredient.DoesNotExist:
        return JsonResponse({'error': 'not found'}, status=404)


def _check_api_token(request):
    """Sprawdza token w nagłówku Authorization: Bearer <token>."""
    token = getattr(settings, 'OFERTY_API_TOKEN', '')
    if not token:
        return False
    auth = request.headers.get('Authorization', '')
    return auth == 'Bearer ' + token


@csrf_exempt
def api_recipes(request):
    """
    GET /api/v1/recipes/
    Zwraca listę aktywnych przepisów z danymi FC dla oferty.sudomie.pl.
    Wymaga nagłówka: Authorization: Bearer <OFERTY_API_TOKEN>
    """
    if not _check_api_token(request):
        return JsonResponse({'error': 'unauthorized'}, status=401)

    recipes = Recipe.objects.filter(is_active=True).prefetch_related('ingredients__ingredient')

    data = []
    for r in recipes:
        cpp = r.cost_per_portion
        data.append({
            'id': r.id,
            'name': r.name,
            'meal_type': r.meal_type,
            'meal_type_display': r.get_meal_type_display(),
            'cost_per_portion': float(cpp) if cpp is not None else None,
            'package_price_per_person': float(r.package_price_per_person) if r.package_price_per_person else None,
            'fc_status': r.get_fc_status(),
            'updated_at': r.updated_at.isoformat(),
        })

    return JsonResponse({'recipes': data, 'count': len(data)})
