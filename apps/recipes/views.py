from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, DeleteView

from apps.accounts.decorators import setup_required
from apps.core.mixins import TenantQuerySetMixin
from .models import Menu, RecipeContext, Recipe
from .forms import (
    MenuForm, RecipeContextForm, RecipeForm, make_menu_item_formset, make_recipe_ingredient_formset,
)


class TenantMixin(TenantQuerySetMixin, LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.organization_id:
            return redirect('accounts:setup')
        return super().dispatch(request, *args, **kwargs)


# ── Konteksty ─────────────────────────────────────────────────────────────────

class RecipeContextListView(TenantMixin, ListView):
    model = RecipeContext
    template_name = 'recipes/context_list.html'
    context_object_name = 'contexts'


class RecipeContextDeleteView(TenantMixin, DeleteView):
    model = RecipeContext
    template_name = 'ingredients/confirm_delete.html'
    success_url = reverse_lazy('recipes:context-list')

    def form_valid(self, form):
        messages.success(self.request, 'Kontekst usunięty.')
        return super().form_valid(form)


@login_required
@setup_required
def context_create(request):
    if request.method == 'POST':
        form = RecipeContextForm(request.POST)
        if form.is_valid():
            ctx = form.save(commit=False)
            ctx.organization = request.user.organization
            ctx.save()
            messages.success(request, 'Kontekst serwowania dodany.')
            return redirect('recipes:context-list')
    else:
        form = RecipeContextForm()
    return render(request, 'recipes/context_form.html', {'form': form, 'title': 'Nowy kontekst'})


@login_required
@setup_required
def context_update(request, pk):
    org = request.user.organization
    ctx = get_object_or_404(RecipeContext, pk=pk, organization=org)
    if request.method == 'POST':
        form = RecipeContextForm(request.POST, instance=ctx)
        if form.is_valid():
            form.save()
            messages.success(request, 'Kontekst zaktualizowany.')
            return redirect('recipes:context-list')
    else:
        form = RecipeContextForm(instance=ctx)
    return render(request, 'recipes/context_form.html', {'form': form, 'title': 'Edytuj kontekst'})


# ── Przepisy ──────────────────────────────────────────────────────────────────

class RecipeListView(TenantMixin, ListView):
    model = Recipe
    template_name = 'recipes/recipe_list.html'
    context_object_name = 'recipes'

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related('contexts')
        q = self.request.GET.get('q', '').strip()
        meal_type = self.request.GET.get('meal_type', '').strip()
        if q:
            qs = qs.filter(name__icontains=q)
        if meal_type:
            qs = qs.filter(meal_type=meal_type)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['meal_type'] = self.request.GET.get('meal_type', '')
        from .models import MEAL_TYPE_CHOICES
        ctx['meal_type_choices'] = MEAL_TYPE_CHOICES
        return ctx


@login_required
@setup_required
def recipe_detail(request, pk):
    org = request.user.organization
    recipe = get_object_or_404(
        Recipe.objects.prefetch_related('recipe_ingredients__ingredient', 'recipe_ingredients__preferred_supplier', 'contexts'),
        pk=pk,
        organization=org,
    )
    rows = []
    for ri in recipe.recipe_ingredients.all():
        rows.append({
            'ri': ri,
            'cost': ri.get_cost(),
            'price': ri.get_price(),
        })
    return render(request, 'recipes/recipe_detail.html', {
        'recipe': recipe,
        'rows': rows,
        'total_cost': recipe.total_cost,
        'cost_per_portion': recipe.cost_per_portion,
        'food_cost_pct': recipe.food_cost_pct,
        'fc_status': recipe.fc_status,
    })


@login_required
@setup_required
def recipe_create(request):
    org = request.user.organization
    FormSet = make_recipe_ingredient_formset(org, extra=5)

    if request.method == 'POST':
        form = RecipeForm(org, request.POST)
        formset = FormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            recipe = form.save(commit=False)
            recipe.organization = org
            recipe.save()
            form.save_m2m()
            formset.instance = recipe
            formset.save()
            messages.success(request, f'Przepis „{recipe.name}" został zapisany.')
            return redirect('recipes:recipe-detail', pk=recipe.pk)
    else:
        form = RecipeForm(org)
        formset = FormSet()

    return render(request, 'recipes/recipe_form.html', {
        'form': form,
        'formset': formset,
        'title': 'Nowy przepis',
    })


@login_required
@setup_required
def recipe_update(request, pk):
    org = request.user.organization
    recipe = get_object_or_404(Recipe, pk=pk, organization=org)
    FormSet = make_recipe_ingredient_formset(org, extra=3)

    if request.method == 'POST':
        form = RecipeForm(org, request.POST, instance=recipe)
        formset = FormSet(request.POST, instance=recipe)
        if form.is_valid() and formset.is_valid():
            recipe = form.save()
            formset.save()
            messages.success(request, f'Przepis „{recipe.name}" zaktualizowany.')
            return redirect('recipes:recipe-detail', pk=recipe.pk)
    else:
        form = RecipeForm(org, instance=recipe)
        formset = FormSet(instance=recipe)

    return render(request, 'recipes/recipe_form.html', {
        'form': form,
        'formset': formset,
        'title': f'Edytuj: {recipe.name}',
        'recipe': recipe,
    })


class RecipeDeleteView(TenantMixin, DeleteView):
    model = Recipe
    template_name = 'ingredients/confirm_delete.html'
    success_url = reverse_lazy('recipes:recipe-list')

    def form_valid(self, form):
        messages.success(self.request, 'Przepis usunięty.')
        return super().form_valid(form)


# ── Menu ──────────────────────────────────────────────────────────────────────

class MenuListView(TenantMixin, ListView):
    model = Menu
    template_name = 'recipes/menu_list.html'
    context_object_name = 'menus'


@login_required
@setup_required
def menu_detail(request, pk):
    org = request.user.organization
    menu = get_object_or_404(
        Menu.objects.prefetch_related('items__recipe'),
        pk=pk, organization=org,
    )
    rows = [{'item': item, 'cost': item.get_cost()} for item in menu.items.all()]
    return render(request, 'recipes/menu_detail.html', {
        'menu': menu,
        'rows': rows,
        'total_cost_per_person': menu.total_cost_per_person,
        'food_cost_pct': menu.food_cost_pct,
        'fc_status': menu.fc_status,
        'is_cost_complete': menu.is_cost_complete,
    })


@login_required
@setup_required
def menu_create(request):
    org = request.user.organization
    FormSet = make_menu_item_formset(org, extra=8)

    if request.method == 'POST':
        form = MenuForm(request.POST)
        formset = FormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            menu = form.save(commit=False)
            menu.organization = org
            menu.save()
            formset.instance = menu
            formset.save()
            messages.success(request, f'Menu „{menu.name}" zostało zapisane.')
            return redirect('recipes:menu-detail', pk=menu.pk)
    else:
        form = MenuForm()
        formset = FormSet()

    return render(request, 'recipes/menu_form.html', {
        'form': form, 'formset': formset, 'title': 'Nowe menu',
    })


@login_required
@setup_required
def menu_update(request, pk):
    org = request.user.organization
    menu = get_object_or_404(Menu, pk=pk, organization=org)
    FormSet = make_menu_item_formset(org, extra=3)

    if request.method == 'POST':
        form = MenuForm(request.POST, instance=menu)
        formset = FormSet(request.POST, instance=menu)
        if form.is_valid() and formset.is_valid():
            menu = form.save()
            formset.save()
            messages.success(request, f'Menu „{menu.name}" zaktualizowane.')
            return redirect('recipes:menu-detail', pk=menu.pk)
    else:
        form = MenuForm(instance=menu)
        formset = FormSet(instance=menu)

    return render(request, 'recipes/menu_form.html', {
        'form': form, 'formset': formset, 'title': f'Edytuj: {menu.name}', 'menu': menu,
    })


class MenuDeleteView(TenantMixin, DeleteView):
    model = Menu
    template_name = 'ingredients/confirm_delete.html'
    success_url = reverse_lazy('recipes:menu-list')

    def form_valid(self, form):
        messages.success(self.request, 'Menu usunięte.')
        return super().form_valid(form)
