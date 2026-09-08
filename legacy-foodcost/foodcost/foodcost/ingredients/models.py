from django.db import models
from decimal import Decimal


class Category(models.Model):
    name = models.CharField('Kategoria', max_length=100)
    order = models.PositiveSmallIntegerField('Kolejność', default=0)

    class Meta:
        verbose_name = 'Kategoria'
        verbose_name_plural = 'Kategorie'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Unit(models.TextChoices):
    KG = 'kg', 'kg'
    G = 'g', 'g'
    L = 'l', 'l'
    ML = 'ml', 'ml'
    SZT = 'szt', 'szt'
    OPAK = 'opak', 'opak'


# Przeliczniki jednostek — baza do normalizacji cen
UNIT_CONVERSIONS = {
    ('kg', 'g'): Decimal('1000'),
    ('g', 'kg'): Decimal('0.001'),
    ('l', 'ml'): Decimal('1000'),
    ('ml', 'l'): Decimal('0.001'),
    ('kg', 'kg'): Decimal('1'),
    ('g', 'g'): Decimal('1'),
    ('l', 'l'): Decimal('1'),
    ('ml', 'ml'): Decimal('1'),
    ('szt', 'szt'): Decimal('1'),
    ('opak', 'opak'): Decimal('1'),
}

BASE_UNITS = {
    'kg': 'g',
    'g': 'g',
    'l': 'ml',
    'ml': 'ml',
    'szt': 'szt',
    'opak': 'opak',
}


class Supplier(models.Model):
    name = models.CharField('Nazwa dostawcy', max_length=200)
    contact_name = models.CharField('Osoba kontaktowa', max_length=200, blank=True)
    phone = models.CharField('Telefon', max_length=50, blank=True)
    email = models.EmailField('Email', blank=True)
    notes = models.TextField('Uwagi', blank=True)
    delivery_days = models.CharField(
        'Dni dostaw', max_length=100, blank=True,
        help_text='np. poniedziałek, środa, piątek'
    )
    is_active = models.BooleanField('Aktywny', default=True)

    class Meta:
        verbose_name = 'Dostawca'
        verbose_name_plural = 'Dostawcy'
        ordering = ['name']

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    name = models.CharField('Nazwa składnika', max_length=200)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Kategoria', related_name='ingredients'
    )
    base_unit = models.CharField(
        'Jednostka bazowa', max_length=10,
        choices=Unit.choices, default=Unit.KG
    )
    notes = models.TextField('Uwagi', blank=True)
    is_active = models.BooleanField('Aktywny', default=True)

    class Meta:
        verbose_name = 'Składnik'
        verbose_name_plural = 'Składniki'
        ordering = ['category__order', 'name']

    def __str__(self):
        return self.name

    def get_current_best_price(self):
        """Zwraca najniższą aktualną cenę w jednostce bazowej."""
        prices = self.supplier_prices.filter(is_current=True).order_by('price_per_base_unit')
        return prices.first()

    def get_current_prices(self):
        """Wszystkie aktualne ceny dla składnika."""
        return self.supplier_prices.filter(is_current=True).select_related('supplier')


class SupplierPrice(models.Model):
    ingredient = models.ForeignKey(
        Ingredient, on_delete=models.CASCADE,
        verbose_name='Składnik', related_name='supplier_prices'
    )
    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE,
        verbose_name='Dostawca', related_name='prices'
    )
    price = models.DecimalField('Cena', max_digits=10, decimal_places=2)
    unit = models.CharField('Jednostka cennika', max_length=10, choices=Unit.choices)
    package_size = models.DecimalField(
        'Rozmiar opakowania', max_digits=10, decimal_places=3,
        null=True, blank=True,
        help_text='np. 5 dla kartonu 5kg, zostaw puste jeśli cena per jednostkę'
    )
    price_per_base_unit = models.DecimalField(
        'Cena za jednostkę bazową', max_digits=10, decimal_places=4,
        editable=False
    )
    valid_from = models.DateField('Data aktualizacji', auto_now_add=True)
    is_current = models.BooleanField('Aktualna', default=True)
    is_netto = models.BooleanField('Cena netto', default=True,
        help_text='Zaznacz jeśli cena jest netto (bez VAT). Odznacz jeśli brutto.')
    source_note = models.CharField(
        'Źródło', max_length=200, blank=True,
        help_text='np. "Cennik Makro marzec 2025"'
    )

    class Meta:
        verbose_name = 'Cena dostawcy'
        verbose_name_plural = 'Ceny dostawców'
        ordering = ['-valid_from']

    def __str__(self):
        return f'{self.ingredient} @ {self.supplier}: {self.price} PLN/{self.unit}'

    def save(self, *args, **kwargs):
        # Jeśli oznaczamy jako aktualną — archiwizuj poprzednią cenę tego dostawcy
        if self.is_current and self.pk is None:
            SupplierPrice.objects.filter(
                ingredient=self.ingredient,
                supplier=self.supplier,
                is_current=True
            ).update(is_current=False)

        # Przelicz cenę do jednostki bazowej
        self.price_per_base_unit = self._calculate_base_price()
        super().save(*args, **kwargs)

    def _calculate_base_price(self):
        """Normalizuje cenę do jednostki bazowej składnika."""
        base = BASE_UNITS.get(self.unit, self.unit)
        ingredient_base = BASE_UNITS.get(self.ingredient.base_unit, self.ingredient.base_unit)

        if base != ingredient_base:
            # Brak przelicznika — zwróć surową cenę, admin musi poprawić jednostki
            return self.price

        conversion = UNIT_CONVERSIONS.get((self.unit, ingredient_base), Decimal('1'))

        if self.package_size:
            # cena za opakowanie → cena za jednostkę → cena za jednostkę bazową
            price_per_unit = self.price / self.package_size
        else:
            price_per_unit = self.price

        return (price_per_unit / conversion).quantize(Decimal('0.0001'))
