from decimal import Decimal
from django.db import models
from simple_history.models import HistoricalRecords
from apps.ingredients.models import UNIT_CONVERSIONS, UNIT_CHOICES


MEAL_TYPE_CHOICES = [
    ('breakfast', 'Śniadanie'),
    ('soup', 'Zupa'),
    ('appetizer', 'Przystawka'),
    ('main', 'Danie główne'),
    ('side', 'Dodatek'),
    ('dessert', 'Deser'),
    ('snack', 'Przekąska'),
    ('lunch', 'Lunch'),
    ('dinner', 'Kolacja'),
]


class RecipeContext(models.Model):
    organization = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.CASCADE,
        related_name='recipe_contexts',
        verbose_name='organizacja',
    )
    name = models.CharField('nazwa', max_length=100, help_text='np. Bufet, Karta, Grupy')
    target_fc_pct = models.DecimalField(
        'docelowy FC%',
        max_digits=5,
        decimal_places=2,
        default=Decimal('30.00'),
    )

    class Meta:
        verbose_name = 'kontekst serwowania'
        verbose_name_plural = 'konteksty serwowania'
        ordering = ['name']
        unique_together = [('organization', 'name')]

    def __str__(self):
        return f'{self.name} (target {self.target_fc_pct}%)'


class Recipe(models.Model):
    organization = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.CASCADE,
        related_name='recipes',
        verbose_name='organizacja',
    )
    name = models.CharField('nazwa', max_length=200)
    meal_type = models.CharField('typ posiłku', max_length=20, choices=MEAL_TYPE_CHOICES, default='main')
    contexts = models.ManyToManyField(
        RecipeContext,
        blank=True,
        verbose_name='konteksty serwowania',
    )
    yield_portions = models.DecimalField(
        'liczba porcji',
        max_digits=6,
        decimal_places=2,
        default=Decimal('1'),
    )
    selling_price = models.DecimalField(
        'cena sprzedaży / porcja',
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    package_price_per_person = models.DecimalField(
        'cena pakietowa / osoba',
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    manual_cost_override = models.DecimalField(
        'koszt / porcję (ręcznie)',
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Wpisz, jeśli nie znasz jeszcze rozbicia na składniki — '
                   'zastępuje wyliczenie z listy składników poniżej.',
    )
    notes = models.TextField('notatki', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'przepis'
        verbose_name_plural = 'przepisy'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def has_cost_data(self):
        """Czy jest jakakolwiek podstawa do liczenia kosztu — ręczna cena albo
        chociaż jeden składnik. Bez tego pusty przepis wygląda jak przepis o
        koszcie zero (świetny food cost!), zamiast "jeszcze nie wiadomo"."""
        return self.manual_cost_override is not None or self.recipe_ingredients.exists()

    @property
    def total_cost(self):
        if self.manual_cost_override is not None:
            return self.manual_cost_override * self.yield_portions
        return sum(
            (ri.get_cost() for ri in self.recipe_ingredients.select_related('ingredient')),
            Decimal('0'),
        )

    @property
    def cost_per_portion(self):
        if self.manual_cost_override is not None:
            return self.manual_cost_override
        if not self.yield_portions:
            return Decimal('0')
        return (self.total_cost / self.yield_portions).quantize(Decimal('0.01'))

    @property
    def food_cost_pct(self):
        if not self.selling_price:
            return None
        if not self.selling_price:
            return None
        pct = (self.cost_per_portion / self.selling_price) * 100
        return pct.quantize(Decimal('0.1'))

    @property
    def food_cost_pct_package(self):
        if not self.package_price_per_person:
            return None
        pct = (self.cost_per_portion / self.package_price_per_person) * 100
        return pct.quantize(Decimal('0.1'))

    @property
    def fc_status(self):
        """Status FC% bez kontekstu — używa domyślnego progu 30%."""
        pct = self.food_cost_pct
        if pct is None:
            return 'unknown'
        if pct <= 30:
            return 'ok'
        if pct <= 38:
            return 'warning'
        return 'danger'

    def fc_status_for_context(self, context):
        pct = self.food_cost_pct
        if pct is None:
            return 'unknown'
        target = context.target_fc_pct
        if pct <= target:
            return 'ok'
        if pct <= target + 8:
            return 'warning'
        return 'danger'


class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='recipe_ingredients',
        verbose_name='przepis',
    )
    ingredient = models.ForeignKey(
        'ingredients.Ingredient',
        on_delete=models.PROTECT,
        related_name='recipe_ingredients',
        verbose_name='składnik',
    )
    preferred_supplier = models.ForeignKey(
        'ingredients.Supplier',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='recipe_ingredients',
        verbose_name='preferowany dostawca',
    )
    quantity = models.DecimalField('ilość', max_digits=10, decimal_places=3)
    unit = models.CharField('jednostka', max_length=10, choices=UNIT_CHOICES)
    yield_factor = models.DecimalField(
        'yield factor',
        max_digits=4,
        decimal_places=2,
        default=Decimal('1.00'),
        help_text='Wydajność (np. 0.85 = 15% odpadów). 1.00 = brak odpadów.',
    )
    is_optional = models.BooleanField('opcjonalny', default=False)
    notes = models.CharField('notatki', max_length=200, blank=True)
    order = models.PositiveSmallIntegerField('kolejność', default=0)

    class Meta:
        verbose_name = 'składnik przepisu'
        verbose_name_plural = 'składniki przepisu'
        ordering = ['order', 'ingredient__name']

    def __str__(self):
        return f'{self.ingredient} × {self.quantity} {self.unit}'

    def get_price(self):
        """Zwraca cenę per jednostka bazowa — od preferowanego dostawcy lub najtańszego."""
        ingredient = self.ingredient
        if self.preferred_supplier_id:
            price = ingredient.prices.filter(
                supplier=self.preferred_supplier,
                is_current=True,
            ).first()
            if price:
                return price.price_per_base_unit
        return ingredient.get_best_price()

    def get_cost(self):
        """Koszt tego składnika w przepisie z uwzględnieniem yield factor."""
        price_per_base = self.get_price()
        if price_per_base is None:
            return Decimal('0')

        base_unit = self.ingredient.base_unit
        factor = UNIT_CONVERSIONS.get(self.unit, {}).get(base_unit)

        if factor is None:
            quantity_in_base = self.quantity
        else:
            quantity_in_base = self.quantity * factor

        if not self.yield_factor or self.yield_factor == 0:
            return Decimal('0')

        actual_quantity = quantity_in_base / self.yield_factor
        return (price_per_base * actual_quantity).quantize(Decimal('0.0001'))


class Menu(models.Model):
    """Pakiet na wydarzenie (np. 'Wigilia firmowa — Menu 1') złożony z wielu
    Przepisów (dań) — trzeci poziom hierarchii Menu / Przepis / Składniki.
    Zanim to dodano, przepis MYLNIE reprezentował całe menu, a danie
    (które samo jest przepisem) trafiało jako Składnik — patrz HANDOFF."""

    organization = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.CASCADE,
        related_name='menus',
        verbose_name='organizacja',
    )
    name = models.CharField('nazwa', max_length=200)
    package_price_per_person = models.DecimalField(
        'cena pakietowa / osoba',
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    target_fc_pct = models.DecimalField(
        'docelowy FC%',
        max_digits=5,
        decimal_places=2,
        default=Decimal('30.00'),
    )
    notes = models.TextField('notatki', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'menu'
        verbose_name_plural = 'menu'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def is_cost_complete(self):
        """False, jeśli choć jedno danie w menu nie ma jeszcze żadnej
        podstawy kosztowej — inaczej suma po cichu liczy brakujące dania
        jako 0 zł, co zaniża food cost całego menu."""
        return all(item.recipe.has_cost_data for item in self.items.select_related('recipe'))

    @property
    def total_cost_per_person(self):
        return sum(
            (item.get_cost() for item in self.items.select_related('recipe')),
            Decimal('0'),
        )

    @property
    def food_cost_pct(self):
        if not self.package_price_per_person:
            return None
        pct = (self.total_cost_per_person / self.package_price_per_person) * 100
        return pct.quantize(Decimal('0.1'))

    @property
    def fc_status(self):
        pct = self.food_cost_pct
        if pct is None:
            return 'unknown'
        if pct <= self.target_fc_pct:
            return 'ok'
        if pct <= self.target_fc_pct + 8:
            return 'warning'
        return 'danger'


class MenuItem(models.Model):
    """Jedno danie (Przepis) wchodzące w skład Menu, z ilością porcji na gościa."""

    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name='items', verbose_name='menu')
    recipe = models.ForeignKey(
        Recipe, on_delete=models.PROTECT, related_name='menu_items', verbose_name='przepis (danie)',
    )
    quantity = models.DecimalField(
        'ilość porcji / gościa', max_digits=6, decimal_places=2, default=Decimal('1'),
    )
    order = models.PositiveSmallIntegerField('kolejność', default=0)

    class Meta:
        verbose_name = 'pozycja menu'
        verbose_name_plural = 'pozycje menu'
        ordering = ['order', 'recipe__name']

    def __str__(self):
        return f'{self.recipe} × {self.quantity}'

    def get_cost(self):
        return (self.recipe.cost_per_portion * self.quantity).quantize(Decimal('0.01'))
