from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy

from apps.accounts.decorators import setup_required
from apps.core.mixins import TenantQuerySetMixin
from .models import Category, Supplier, Ingredient, SupplierPrice
from .forms import CategoryForm, SupplierForm, IngredientForm, SupplierPriceForm


class TenantMixin(TenantQuerySetMixin, LoginRequiredMixin):
    """Łączy tenant isolation z wymogiem logowania."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.organization_id:
            return redirect('accounts:setup')
        return super().dispatch(request, *args, **kwargs)


# ── Kategorie ────────────────────────────────────────────────────────────────

class CategoryListView(TenantMixin, ListView):
    model = Category
    template_name = 'ingredients/category_list.html'
    context_object_name = 'categories'


class CategoryCreateView(TenantMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'ingredients/category_form.html'
    success_url = reverse_lazy('ingredients:category-list')

    def form_valid(self, form):
        form.instance.organization = self.request.user.organization
        messages.success(self.request, 'Kategoria została dodana.')
        return super().form_valid(form)


class CategoryUpdateView(TenantMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'ingredients/category_form.html'
    success_url = reverse_lazy('ingredients:category-list')

    def form_valid(self, form):
        messages.success(self.request, 'Kategoria została zaktualizowana.')
        return super().form_valid(form)


class CategoryDeleteView(TenantMixin, DeleteView):
    model = Category
    template_name = 'ingredients/confirm_delete.html'
    success_url = reverse_lazy('ingredients:category-list')

    def form_valid(self, form):
        messages.success(self.request, 'Kategoria została usunięta.')
        return super().form_valid(form)


# ── Dostawcy ─────────────────────────────────────────────────────────────────

class SupplierListView(TenantMixin, ListView):
    model = Supplier
    template_name = 'ingredients/supplier_list.html'
    context_object_name = 'suppliers'


class SupplierCreateView(TenantMixin, CreateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'ingredients/supplier_form.html'
    success_url = reverse_lazy('ingredients:supplier-list')

    def form_valid(self, form):
        form.instance.organization = self.request.user.organization
        messages.success(self.request, 'Dostawca został dodany.')
        return super().form_valid(form)


class SupplierUpdateView(TenantMixin, UpdateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'ingredients/supplier_form.html'
    success_url = reverse_lazy('ingredients:supplier-list')

    def form_valid(self, form):
        messages.success(self.request, 'Dostawca został zaktualizowany.')
        return super().form_valid(form)


class SupplierDeleteView(TenantMixin, DeleteView):
    model = Supplier
    template_name = 'ingredients/confirm_delete.html'
    success_url = reverse_lazy('ingredients:supplier-list')

    def form_valid(self, form):
        messages.success(self.request, 'Dostawca został usunięty.')
        return super().form_valid(form)


# ── Składniki ─────────────────────────────────────────────────────────────────

class IngredientListView(TenantMixin, ListView):
    model = Ingredient
    template_name = 'ingredients/ingredient_list.html'
    context_object_name = 'ingredients'

    def get_queryset(self):
        qs = super().get_queryset().select_related('category')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


class IngredientCreateView(TenantMixin, CreateView):
    model = Ingredient
    template_name = 'ingredients/ingredient_form.html'
    success_url = reverse_lazy('ingredients:ingredient-list')

    def get_form(self, form_class=None):
        return IngredientForm(self.request.user.organization, **self.get_form_kwargs())

    def form_valid(self, form):
        form.instance.organization = self.request.user.organization
        messages.success(self.request, 'Składnik został dodany.')
        return super().form_valid(form)


class IngredientUpdateView(TenantMixin, UpdateView):
    model = Ingredient
    template_name = 'ingredients/ingredient_form.html'
    success_url = reverse_lazy('ingredients:ingredient-list')

    def get_form(self, form_class=None):
        return IngredientForm(self.request.user.organization, **self.get_form_kwargs())

    def form_valid(self, form):
        messages.success(self.request, 'Składnik został zaktualizowany.')
        return super().form_valid(form)


class IngredientDeleteView(TenantMixin, DeleteView):
    model = Ingredient
    template_name = 'ingredients/confirm_delete.html'
    success_url = reverse_lazy('ingredients:ingredient-list')

    def form_valid(self, form):
        messages.success(self.request, 'Składnik został usunięty.')
        return super().form_valid(form)


# ── Ceny składnika ────────────────────────────────────────────────────────────

@login_required
@setup_required
def ingredient_detail(request, pk):
    org = request.user.organization
    ingredient = get_object_or_404(Ingredient, pk=pk, organization=org)
    prices = ingredient.get_current_prices()

    if request.method == 'POST':
        form = SupplierPriceForm(org, request.POST)
        if form.is_valid():
            price = form.save(commit=False)
            price.ingredient = ingredient
            price.save()
            messages.success(request, 'Cena została zaktualizowana.')
            return redirect('ingredients:ingredient-detail', pk=pk)
    else:
        form = SupplierPriceForm(org)

    return render(request, 'ingredients/ingredient_detail.html', {
        'ingredient': ingredient,
        'prices': prices,
        'form': form,
        'price_history': ingredient.prices.filter(is_current=False).select_related('supplier').order_by('-valid_from')[:10],
    })


# ── API dla Alpine.js ─────────────────────────────────────────────────────────

@login_required
@setup_required
def api_ingredient_price(request, pk):
    org = request.user.organization
    ingredient = get_object_or_404(Ingredient, pk=pk, organization=org)

    supplier_id = request.GET.get('supplier')
    if supplier_id:
        price = ingredient.prices.filter(supplier_id=supplier_id, is_current=True).first()
    else:
        price = ingredient.prices.filter(is_current=True).order_by('price_per_base_unit').first()

    return JsonResponse({
        'price_per_base_unit': str(price.price_per_base_unit) if price else None,
        'base_unit': ingredient.base_unit,
        'has_price': price is not None,
    })
