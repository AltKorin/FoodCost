from decimal import Decimal
from django.db import models
from simple_history.models import HistoricalRecords

UNIT_CHOICES = [
    ('kg', 'kg'),
    ('g', 'g'),
    ('l', 'l'),
    ('ml', 'ml'),
    ('szt', 'szt'),
    ('opak', 'opak'),
]

# Ile jednostek bazowych mieści się w 1 jednostce źródłowej
# UNIT_CONVERSIONS[from_unit][to_unit] = współczynnik
UNIT_CONVERSIONS = {
    'g':    {'kg': Decimal('0.001'),  'g': Decimal('1')},
    'kg':   {'kg': Decimal('1'),      'g': Decimal('1000')},
    'ml':   {'l':  Decimal('0.001'),  'ml': Decimal('1')},
    'l':    {'l':  Decimal('1'),      'ml': Decimal('1000')},
    'szt':  {'szt': Decimal('1')},
    'opak': {'opak': Decimal('1')},
}


def convert_quantity(quantity, from_unit, to_unit):
    """Przelicza ilość z jednej jednostki na inną. Zwraca None gdy konwersja niemożliwa."""
    if from_unit == to_unit:
        return quantity
    factor = UNIT_CONVERSIONS.get(from_unit, {}).get(to_unit)
    if factor is None:
        return None
    return quantity * factor


class Category(models.Model):
    organization = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.CASCADE,
        related_name='categories',
    )
    name = models.CharField('nazwa', max_length=100)
    order = models.PositiveSmallIntegerField('kolejność', default=0)

    class Meta:
        verbose_name = 'kategoria'
        verbose_name_plural = 'kategorie'
        ordering = ['order', 'name']
        unique_together = [('organization', 'name')]

    def __str__(self):
        return self.name


class Supplier(models.Model):
    organization = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.CASCADE,
        related_name='suppliers',
    )
    name = models.CharField('nazwa', max_length=200)
    contact_name = models.CharField('osoba kontaktowa', max_length=100, blank=True)
    phone = models.CharField('telefon', max_length=20, blank=True)
    email = models.EmailField('e-mail', blank=True)
    notes = models.TextField('notatki', blank=True)
    delivery_days = models.CharField('dni dostaw', max_length=100, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'dostawca'
        verbose_name_plural = 'dostawcy'
        ordering = ['name']

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    organization = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.CASCADE,
        related_name='ingredients',
    )
    name = models.CharField('nazwa', max_length=200)
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='ingredients',
        verbose_name='kategoria',
    )
    base_unit = models.CharField('jednostka bazowa', max_length=10, choices=UNIT_CHOICES, default='kg')
    notes = models.TextField('notatki', blank=True)
    is_active = models.BooleanField('aktywny', default=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'składnik'
        verbose_name_plural = 'składniki'
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_best_price(self):
        """Zwraca najtańszą aktualną cenę per jednostka bazowa."""
        price = self.prices.filter(is_current=True).order_by('price_per_base_unit').first()
        return price.price_per_base_unit if price else None

    def get_current_prices(self):
        return self.prices.filter(is_current=True).select_related('supplier').order_by('price_per_base_unit')


class SupplierPrice(models.Model):
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        related_name='prices',
        verbose_name='składnik',
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name='prices',
        verbose_name='dostawca',
    )
    price = models.DecimalField('cena', max_digits=10, decimal_places=2)
    unit = models.CharField('jednostka', max_length=10, choices=UNIT_CHOICES)
    package_size = models.DecimalField(
        'rozmiar opakowania',
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        help_text='Ile jednostek w opakowaniu (np. 25 dla worka 25 kg)',
    )
    price_per_base_unit = models.DecimalField(
        'cena / jednostka bazowa',
        max_digits=10,
        decimal_places=4,
        editable=False,
        default=Decimal('0'),
    )
    is_netto = models.BooleanField('cena netto', default=True)
    is_current = models.BooleanField('aktualna', default=True, editable=False)
    valid_from = models.DateTimeField('ważna od', auto_now_add=True)
    source_note = models.CharField('źródło', max_length=200, blank=True)

    class Meta:
        verbose_name = 'cena dostawcy'
        verbose_name_plural = 'ceny dostawców'
        ordering = ['-valid_from']
        indexes = [
            models.Index(fields=['ingredient', 'supplier', 'is_current']),
        ]

    def __str__(self):
        return f'{self.supplier} — {self.ingredient}: {self.price} / {self.unit}'

    def _calculate_price_per_base_unit(self):
        base_unit = self.ingredient.base_unit
        qty = self.package_size if self.package_size else Decimal('1')

        if self.unit == 'opak':
            if not self.package_size:
                return self.price
            return self.price / self.package_size

        factor = UNIT_CONVERSIONS.get(self.unit, {}).get(base_unit)
        if factor is None:
            return self.price
        # price jest za qty jednostek (self.unit)
        # qty * factor = ile base_unit mamy
        return self.price / (qty * factor)

    def save(self, *args, **kwargs):
        # Archiwizuj poprzednią aktualną cenę tego samego składnika u tego samego dostawcy
        SupplierPrice.objects.filter(
            ingredient=self.ingredient,
            supplier=self.supplier,
            is_current=True,
        ).exclude(pk=self.pk).update(is_current=False)

        self.is_current = True
        self.price_per_base_unit = self._calculate_price_per_base_unit()
        super().save(*args, **kwargs)
