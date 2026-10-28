from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class Offer(models.Model):
    organization = models.ForeignKey('accounts.Organization', on_delete=models.CASCADE, related_name='offers')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    seller_name = models.CharField('Nazwa lokalu', max_length=200)
    seller_details = models.TextField('Dane lokalu / kontakt', blank=True)
    title = models.CharField('Nazwa wydarzenia', max_length=200)
    client_name = models.CharField('Klient / organizator', max_length=200)
    client_email = models.EmailField('E-mail klienta', blank=True)
    client_details = models.TextField('Dane klienta', blank=True)
    date_from = models.DateField('Wydarzenie od')
    date_to = models.DateField('Wydarzenie do')
    persons = models.PositiveIntegerField('Liczba osób', validators=[MinValueValidator(1)])
    valid_until = models.DateField('Oferta ważna do', null=True, blank=True)
    status = models.CharField('Status', max_length=12, default='draft', choices=[('draft', 'Szkic'), ('sent', 'Wysłana'), ('accepted', 'Zaakceptowana'), ('rejected', 'Odrzucona'), ('cancelled', 'Anulowana')])
    deposit_pct = models.DecimalField('Wpłata wstępna (%)', max_digits=5, decimal_places=2, default=30, validators=[MinValueValidator(0), MaxValueValidator(100)])
    terms = models.TextField('Warunki i uwagi dla klienta', blank=True)
    internal_notes = models.TextField('Notatki wewnętrzne', blank=True)
    revision = models.PositiveIntegerField(default=1, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def number(self):
        return f'OG/{self.created_at.year}/{self.pk:05d}'

    @property
    def total(self):
        return sum((line.total for line in self.lines.all()), Decimal('0.00'))

    @property
    def deposit(self):
        return (self.total * self.deposit_pct / 100).quantize(Decimal('0.01'))

    @property
    def gastronomy_total(self):
        return sum((line.total for line in self.lines.all() if line.kind == 'menu'), Decimal('0.00'))

    @property
    def gastronomy_cost(self):
        return sum((line.cost_per_unit * line.quantity for line in self.lines.all() if line.kind == 'menu' and line.cost_per_unit is not None), Decimal('0.00')).quantize(Decimal('0.01'))

    @property
    def cost_complete(self):
        menus = [line for line in self.lines.all() if line.kind == 'menu']
        return bool(menus) and all(line.cost_complete for line in menus)

    @property
    def food_cost_pct(self):
        if not self.cost_complete or not self.gastronomy_total:
            return None
        return (self.gastronomy_cost / self.gastronomy_total * 100).quantize(Decimal('0.1'))


class OfferLine(models.Model):
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='lines')
    kind = models.CharField('Rodzaj', max_length=12, choices=[('menu', 'Wyżywienie'), ('room', 'Noclegi'), ('service', 'Usługi dodatkowe')], default='menu')
    menu = models.ForeignKey('recipes.Menu', null=True, blank=True, on_delete=models.SET_NULL)
    description = models.CharField('Nazwa pozycji', max_length=200, blank=True)
    details = models.TextField('Opis dla klienta', blank=True)
    quantity = models.DecimalField('Ilość', max_digits=10, decimal_places=2, default=1, validators=[MinValueValidator(Decimal('0.01'))])
    unit = models.CharField('Jednostka', max_length=40, default='os.')
    unit_price = models.DecimalField('Cena jednostkowa (zł)', max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    cost_per_unit = models.DecimalField(max_digits=12, decimal_places=2, null=True, editable=False)
    cost_complete = models.BooleanField(default=False, editable=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'pk']

    @property
    def total(self):
        return (self.quantity * self.unit_price).quantize(Decimal('0.01'))
