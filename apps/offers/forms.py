from django import forms
from django.forms import inlineformset_factory
from apps.recipes.models import Menu
from .models import Offer, OfferLine


def style(form):
    for field in form.fields.values():
        field.widget.attrs['class'] = ('form-check-input' if isinstance(field.widget, forms.CheckboxInput) else 'form-select' if isinstance(field.widget, forms.Select) else 'form-control')
        if isinstance(field.widget, forms.Textarea):
            field.widget.attrs['rows'] = 2


class OfferForm(forms.ModelForm):
    revision = forms.IntegerField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = Offer
        fields = ['title', 'client_name', 'client_email', 'client_details', 'seller_name', 'seller_details', 'date_from', 'date_to', 'persons', 'valid_until', 'status', 'deposit_pct', 'terms', 'internal_notes']
        widgets = {key: forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d') for key in ['date_from', 'date_to', 'valid_until']}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style(self)
        self.fields['revision'].initial = self.instance.revision

    def clean(self):
        data = super().clean()
        if data.get('date_from') and data.get('date_to') and data['date_to'] < data['date_from']:
            self.add_error('date_to', 'Data końcowa nie może być wcześniejsza niż początkowa.')
        return data


class LineForm(forms.ModelForm):
    refresh_menu = forms.BooleanField(label='Pobierz aktualną treść i koszt menu z FC', required=False, help_text='Cena sprzedaży pozostaje taka, jak wpisano w ofercie.')

    class Meta:
        model = OfferLine
        fields = ['kind', 'menu', 'description', 'details', 'quantity', 'unit', 'unit_price']

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['menu'].queryset = Menu.objects.filter(organization=organization) if organization else Menu.objects.none()
        self.fields['unit_price'].required = False
        self.fields['menu'].help_text = 'Opcjonalnie wybierz menu FC. Pusta cena pobierze cenę menu.'
        style(self)
        self.fields['refresh_menu'].widget.attrs['class'] = 'form-check-input'

    def clean(self):
        data = super().clean()
        menu = data.get('menu')
        if menu and data.get('kind') != 'menu':
            self.add_error('menu', 'Menu FC można wybrać tylko dla wyżywienia.')
        if not menu and not data.get('description'):
            self.add_error('description', 'Podaj nazwę pozycji lub wybierz menu FC.')
        if data.get('unit_price') is None:
            if menu and menu.package_price_per_person is not None:
                data['unit_price'] = menu.package_price_per_person
                self.instance.unit_price = data['unit_price']
            else:
                self.add_error('unit_price', 'Wpisz cenę sprzedaży tej pozycji.')
        return data


LineFormSet = inlineformset_factory(Offer, OfferLine, form=LineForm, extra=0, can_delete=True, min_num=1, validate_min=True, max_num=100, validate_max=True)
