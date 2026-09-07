from django import forms
from django.forms import inlineformset_factory
from .models import Menu, MenuItem, RecipeContext, Recipe, RecipeIngredient
from apps.ingredients.models import UNIT_CHOICES


class RecipeCostSelect(forms.Select):
    """`data-cost`/`data-has-cost` per <option>, żeby menu_form.html mogło
    liczyć podgląd kosztu w JS bez fetcha — koszt/porcję jest już znany po
    stronie serwera, nie zależy od nic wybieranego w tym formularzu (w
    przeciwieństwie do ceny składnika, która zależy od dostawcy)."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        cost_map = getattr(self, 'cost_map', {})
        pk = value.value if hasattr(value, 'value') else value
        if pk in cost_map:
            cost, has_cost = cost_map[pk]
            option['attrs']['data-cost'] = str(cost)
            option['attrs']['data-has-cost'] = 'true' if has_cost else 'false'
        return option


class RecipeContextForm(forms.ModelForm):
    class Meta:
        model = RecipeContext
        fields = ('name', 'target_fc_pct')
        labels = {'name': 'Nazwa kontekstu', 'target_fc_pct': 'Docelowy FC% (%)'}
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True, 'placeholder': 'np. Karta, Bufet, Grupy'}),
            'target_fc_pct': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': '1', 'max': '100'}),
        }


class RecipeForm(forms.ModelForm):
    def __init__(self, organization, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['contexts'].queryset = RecipeContext.objects.filter(organization=organization)

    class Meta:
        model = Recipe
        fields = (
            'name', 'meal_type', 'contexts', 'yield_portions', 'selling_price',
            'package_price_per_person', 'manual_cost_override', 'notes',
        )
        labels = {
            'name': 'Nazwa przepisu',
            'meal_type': 'Typ posiłku',
            'contexts': 'Konteksty serwowania',
            'yield_portions': 'Liczba porcji',
            'selling_price': 'Cena sprzedaży / porcja (PLN)',
            'package_price_per_person': 'Cena pakietowa / osoba (PLN)',
            'manual_cost_override': 'Koszt / porcję ręcznie (PLN)',
            'notes': 'Notatki',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'meal_type': forms.Select(attrs={'class': 'form-select'}),
            'contexts': forms.CheckboxSelectMultiple(),
            'yield_portions': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': '0.5'}),
            'selling_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'package_price_per_person': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'manual_cost_override': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class RecipeIngredientForm(forms.ModelForm):
    def __init__(self, organization=None, *args, **kwargs):
        # `organization=None` bo BaseFormSet konstruuje ten formularz wewnętrznie
        # przez `self.form(**defaults)` bez żadnego sposobu na wstrzyknięcie
        # dodatkowego argumentu — `make_recipe_ingredient_formset.BoundFormSet`
        # i tak nadpisuje queryset zaraz po konstrukcji, dla KAŻDEGO formularza.
        super().__init__(*args, **kwargs)
        if organization is not None:
            from apps.ingredients.models import Ingredient, Supplier
            self.fields['ingredient'].queryset = Ingredient.objects.filter(
                organization=organization, is_active=True
            ).select_related('category').order_by('name')
            self.fields['preferred_supplier'].queryset = Supplier.objects.filter(organization=organization)

    def has_changed(self):
        # Pusty dodatkowy wiersz i tak dostaje `unit` (przeglądarka domyślnie
        # wysyła pierwszą opcję <select>) i `yield_factor` (initial z domyślnej
        # wartości modelu) — bez tego Django uznaje taki wiersz za "zmieniony"
        # i wymusza wypełnienie `ingredient`, mimo że użytkownik zostawił go
        # w całości pustym.
        if not self.data.get(self.add_prefix('ingredient')):
            return False
        return super().has_changed()

    class Meta:
        model = RecipeIngredient
        fields = ('ingredient', 'quantity', 'unit', 'yield_factor', 'preferred_supplier', 'is_optional', 'notes')
        widgets = {
            'ingredient': forms.Select(attrs={'class': 'form-select form-select-sm ri-ingredient'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.001', 'min': '0'}),
            'unit': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'yield_factor': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01', 'min': '0.01', 'max': '1'}),
            'preferred_supplier': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'is_optional': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
        }


class MenuForm(forms.ModelForm):
    class Meta:
        model = Menu
        fields = ('name', 'package_price_per_person', 'target_fc_pct', 'notes')
        labels = {
            'name': 'Nazwa menu',
            'package_price_per_person': 'Cena pakietowa / osoba (PLN)',
            'target_fc_pct': 'Docelowy FC% (%)',
            'notes': 'Notatki',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'package_price_per_person': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'target_fc_pct': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': '1', 'max': '100'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


def _set_recipe_field_for_menu(field, organization):
    recipes = list(
        Recipe.objects.filter(organization=organization)
        .prefetch_related('recipe_ingredients')
        .order_by('name'),
    )
    field.queryset = Recipe.objects.filter(pk__in=[r.pk for r in recipes])
    field.widget.cost_map = {
        r.pk: (r.cost_per_portion, r.manual_cost_override is not None or bool(r.recipe_ingredients.all()))
        for r in recipes
    }


class MenuItemForm(forms.ModelForm):
    def __init__(self, organization=None, *args, **kwargs):
        # Ten sam wzorzec co RecipeIngredientForm — BaseFormSet konstruuje
        # formularz przez `self.form(**defaults)`, `organization` doklejane
        # dopiero po fakcie przez BoundFormSet._construct_form.
        super().__init__(*args, **kwargs)
        if organization is not None:
            _set_recipe_field_for_menu(self.fields['recipe'], organization)

    def has_changed(self):
        if not self.data.get(self.add_prefix('recipe')):
            return False
        return super().has_changed()

    class Meta:
        model = MenuItem
        fields = ('recipe', 'quantity')
        widgets = {
            'recipe': RecipeCostSelect(attrs={'class': 'form-select form-select-sm'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.5', 'min': '0'}),
        }


def make_menu_item_formset(organization, extra=5):
    BaseFormSet = inlineformset_factory(
        Menu, MenuItem, form=MenuItemForm, fields=('recipe', 'quantity'), extra=extra, can_delete=True,
    )

    class BoundFormSet(BaseFormSet):
        def _construct_form(self, i, **kwargs):
            form = super()._construct_form(i, **kwargs)
            _set_recipe_field_for_menu(form.fields['recipe'], organization)
            return form

    return BoundFormSet


def make_recipe_ingredient_formset(organization, extra=3):
    BaseFormSet = inlineformset_factory(
        Recipe,
        RecipeIngredient,
        form=RecipeIngredientForm,
        fields=('ingredient', 'quantity', 'unit', 'yield_factor', 'preferred_supplier', 'is_optional', 'notes'),
        extra=extra,
        can_delete=True,
    )

    class BoundFormSet(BaseFormSet):
        def _construct_form(self, i, **kwargs):
            form = super()._construct_form(i, **kwargs)
            from apps.ingredients.models import Ingredient, Supplier
            form.fields['ingredient'].queryset = Ingredient.objects.filter(
                organization=organization, is_active=True
            ).select_related('category').order_by('name')
            form.fields['preferred_supplier'].queryset = Supplier.objects.filter(organization=organization)
            return form

    return BoundFormSet
