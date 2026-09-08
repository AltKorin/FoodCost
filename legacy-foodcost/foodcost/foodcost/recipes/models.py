from django.db import models
from decimal import Decimal


class MenuContext(models.TextChoices):
    BUFFET = 'buffet', 'Bufet'
    GROUP = 'group', 'Grupy'
    A_LA_CARTE = 'carte', 'Karta'


class MealType(models.TextChoices):
    BREAKFAST = 'breakfast', 'Śniadanie'
    LUNCH = 'lunch', 'Obiad'
    DINNER = 'dinner', 'Kolacja'
    SOUP = 'soup', 'Zupa'
    APPETIZER = 'appetizer', 'Przystawka'
    MAIN = 'main', 'Danie główne'
    DESSERT = 'dessert', 'Deser'
    SNACK = 'snack', 'Przekąska'
    SIDE = 'side', 'Dodatek'


class Recipe(models.Model):
    name = models.CharField('Nazwa dania', max_length=200)
    description = models.TextField('Opis', blank=True)
    meal_type = models.CharField(
        'Rodzaj posiłku', max_length=20,
        choices=MealType.choices, default=MealType.MAIN
    )
    # Konteksty serwowania — M2M przez pośrednią tabelę
    contexts = models.ManyToManyField(
        'RecipeContext', verbose_name='Konteksty', blank=True
    )
    yield_portions = models.DecimalField(
        'Liczba porcji', max_digits=6, decimal_places=1, default=1
    )
    selling_price = models.DecimalField(
        'Cena sprzedaży (PLN)', max_digits=8, decimal_places=2,
        null=True, blank=True
    )
    # Dla bufetu i grup: cena pakietu per osobę
    package_price_per_person = models.DecimalField(
        'Cena pakietu/os (PLN)', max_digits=8, decimal_places=2,
        null=True, blank=True,
        help_text='Dla bufetu i grup — cena serwisu per osoba'
    )
    notes = models.TextField('Uwagi kuchenne', blank=True)
    is_active = models.BooleanField('Aktywny', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Przepis'
        verbose_name_plural = 'Przepisy'
        ordering = ['meal_type', 'name']

    def __str__(self):
        return self.name

    @property
    def total_cost(self):
        """Łączny koszt wszystkich składników przepisu."""
        total = Decimal('0')
        for ri in self.ingredients.select_related('ingredient'):
            cost = ri.get_cost()
            if cost is not None:
                total += cost
        return total

    @property
    def cost_per_portion(self):
        """Koszt jednej porcji."""
        if self.yield_portions and self.yield_portions > 0:
            return (self.total_cost / self.yield_portions).quantize(Decimal('0.01'))
        return None

    @property
    def food_cost_percentage(self):
        """FC% względem ceny sprzedaży."""
        cpp = self.cost_per_portion
        if cpp and self.selling_price and self.selling_price > 0:
            return (cpp / self.selling_price * 100).quantize(Decimal('0.1'))
        return None

    @property
    def food_cost_percentage_package(self):
        """FC% względem ceny pakietu (bufet/grupy)."""
        cpp = self.cost_per_portion
        if cpp and self.package_price_per_person and self.package_price_per_person > 0:
            return (cpp / self.package_price_per_person * 100).quantize(Decimal('0.1'))
        return None

    def get_fc_status(self):
        """Zwraca 'ok', 'warning', 'danger' na podstawie celów FC."""
        fc = self.food_cost_percentage
        if fc is None:
            return 'unknown'
        if fc <= 30:
            return 'ok'
        elif fc <= 38:
            return 'warning'
        return 'danger'


class RecipeContext(models.Model):
    """Kontekst serwowania — osobna tabela żeby móc dodawać metadane."""
    context = models.CharField(
        'Kontekst', max_length=20,
        choices=MenuContext.choices, unique=True
    )
    target_fc_percentage = models.DecimalField(
        'Docelowy FC%', max_digits=5, decimal_places=1,
        default=Decimal('30.0')
    )

    class Meta:
        verbose_name = 'Kontekst menu'
        verbose_name_plural = 'Konteksty menu'

    def __str__(self):
        return self.get_context_display()


class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(
        Recipe, on_delete=models.CASCADE,
        related_name='ingredients', verbose_name='Przepis'
    )
    ingredient = models.ForeignKey(
        'ingredients.Ingredient', on_delete=models.PROTECT,
        related_name='used_in', verbose_name='Składnik'
    )
    preferred_supplier = models.ForeignKey(
        'ingredients.Supplier', on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Wybrany dostawca',
        help_text='Jeśli puste — używa najtańszego dostawcy automatycznie'
    )
    quantity = models.DecimalField('Ilość', max_digits=10, decimal_places=3)
    unit = models.CharField('Jednostka', max_length=10,
                            choices=[('g', 'g'), ('kg', 'kg'), ('ml', 'ml'),
                                     ('l', 'l'), ('szt', 'szt'), ('opak', 'opak')])
    yield_factor = models.DecimalField(
        'Wydajność', max_digits=4, decimal_places=2, default=Decimal('1.00'),
        help_text='Procent użytkowy (np. 0.85 dla ziemniaków po obraniu)'
    )
    is_optional = models.BooleanField('Opcjonalny', default=False)
    notes = models.CharField('Uwagi', max_length=200, blank=True)

    class Meta:
        verbose_name = 'Składnik przepisu'
        verbose_name_plural = 'Składniki przepisu'
        ordering = ['ingredient__name']

    def __str__(self):
        return f'{self.quantity}{self.unit} {self.ingredient}'

    def get_price(self):
        """Zwraca cenę wg wybranego dostawcy lub najtańszego."""
        if self.preferred_supplier:
            price = self.ingredient.supplier_prices.filter(
                supplier=self.preferred_supplier,
                is_current=True
            ).first()
            if price:
                return price
        return self.ingredient.get_current_best_price()

    def get_cost(self):
        """Koszt tego składnika w przepisie."""
        from ingredients.models import UNIT_CONVERSIONS, BASE_UNITS
        price = self.get_price()
        if not price:
            return None

        base_unit = BASE_UNITS.get(self.unit, self.unit)
        ingredient_base = BASE_UNITS.get(self.ingredient.base_unit, self.ingredient.base_unit)

        if base_unit != ingredient_base:
            return None

        conversion = UNIT_CONVERSIONS.get(
            (self.unit, ingredient_base), Decimal('1')
        )
        quantity_in_base = self.quantity * conversion
        effective_quantity = quantity_in_base / self.yield_factor

        return (effective_quantity * price.price_per_base_unit).quantize(Decimal('0.01'))
