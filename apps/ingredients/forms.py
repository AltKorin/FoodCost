from django import forms
from .models import Category, Supplier, Ingredient, SupplierPrice, UNIT_CHOICES


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ('name', 'order')
        labels = {'name': 'Nazwa', 'order': 'Kolejność'}
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ('name', 'contact_name', 'phone', 'email', 'delivery_days', 'notes')
        labels = {
            'name': 'Nazwa dostawcy',
            'contact_name': 'Osoba kontaktowa',
            'phone': 'Telefon',
            'email': 'E-mail',
            'delivery_days': 'Dni dostaw',
            'notes': 'Notatki',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'contact_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'delivery_days': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'np. Pon, Śr, Pt'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class IngredientForm(forms.ModelForm):
    def __init__(self, organization, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(organization=organization)

    class Meta:
        model = Ingredient
        fields = ('name', 'category', 'base_unit', 'notes', 'is_active')
        labels = {
            'name': 'Nazwa',
            'category': 'Kategoria',
            'base_unit': 'Jednostka bazowa',
            'notes': 'Notatki',
            'is_active': 'Aktywny',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'base_unit': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SupplierPriceForm(forms.ModelForm):
    def __init__(self, organization, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supplier'].queryset = Supplier.objects.filter(organization=organization)

    class Meta:
        model = SupplierPrice
        fields = ('supplier', 'price', 'unit', 'package_size', 'is_netto', 'source_note')
        labels = {
            'supplier': 'Dostawca',
            'price': 'Cena (PLN)',
            'unit': 'Jednostka',
            'package_size': 'Rozmiar opakowania',
            'is_netto': 'Cena netto',
            'source_note': 'Źródło ceny',
        }
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'unit': forms.Select(attrs={'class': 'form-select'}),
            'package_size': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0'}),
            'is_netto': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'source_note': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'np. faktura 2025-04'}),
        }
