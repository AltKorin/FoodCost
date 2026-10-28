"""Restauracja Demo. One builder for `manage.py seed` (a fixed demo on a server) and for the sandbox every visitor gets
from „Wypróbuj demo”: an own copy, an account without a password (only this session enters it), erased after DEMO_HOURS.
Invoice OCR stays off in a sandbox — every read costs money at OpenAI (Organization.ocr_available, ocr_access)."""

import secrets
from datetime import timedelta
from decimal import Decimal as D

from django.conf import settings
from django.contrib.auth import login
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Organization, User
from apps.ingredients.models import Category, Ingredient, Supplier, SupplierPrice
from apps.recipes.models import Menu, MenuItem, Recipe, RecipeContext, RecipeIngredient

NAME = 'Restauracja Demo'
INGREDIENTS = [  # name, category, base unit, supplier, price, unit, package size
    ('Ziemniaki', 'Warzywa', 'kg', 'Makro Cash&Carry', '3.20', 'kg', '1'),
    ('Cebula', 'Warzywa', 'kg', 'Makro Cash&Carry', '2.80', 'kg', '1'),
    ('Marchew', 'Warzywa', 'kg', 'Lokalny dostawca warzyw', '2.50', 'kg', '1'),
    ('Pierś z kurczaka', 'Mięso', 'kg', 'Makro Cash&Carry', '18.90', 'kg', '1'),
    ('Schab wieprzowy', 'Mięso', 'kg', 'Makro Cash&Carry', '22.50', 'kg', '1'),
    ('Masło', 'Nabiał', 'kg', 'Makro Cash&Carry', '9.20', 'kg', '1'),
    ('Śmietana 18%', 'Nabiał', 'l', 'Makro Cash&Carry', '7.80', 'l', '1'),
    ('Mleko', 'Nabiał', 'l', 'Makro Cash&Carry', '3.10', 'l', '1'),
    ('Mąka pszenna', 'Sypkie', 'kg', 'Makro Cash&Carry', '4.00', 'opak', '25'),
    ('Sól', 'Sypkie', 'kg', 'Makro Cash&Carry', '1.50', 'kg', '1'),
]
SUPPLIERS = {'Makro Cash&Carry': 'Pon, Śr, Pt', 'Lokalny dostawca warzyw': 'Wt, Czw'}
RECIPES = [  # name, meal type, contexts, selling price, [(ingredient, quantity, unit, yield)]
    ('Kotlet schabowy z ziemniakami', 'main', ['Karta'], '32.00', [
        ('Schab wieprzowy', '0.18', 'kg', '0.90'), ('Ziemniaki', '0.25', 'kg', '1.00'), ('Mąka pszenna', '0.02', 'kg', '1.00')]),
    ('Rosół z kurczaka', 'soup', ['Karta', 'Bufet'], '14.00', [
        ('Pierś z kurczaka', '0.12', 'kg', '0.85'), ('Marchew', '0.05', 'kg', '0.90'), ('Cebula', '0.03', 'kg', '0.90')]),
    ('Naleśniki ze śmietaną', 'dessert', ['Bufet'], '12.00', [
        ('Mleko', '0.15', 'l', '1.00'), ('Mąka pszenna', '0.08', 'kg', '1.00'), ('Śmietana 18%', '0.05', 'l', '1.00'), ('Masło', '0.01', 'kg', '1.00')]),
]
CONTEXTS = {'Karta': '32.00', 'Bufet': '28.00'}


def fill(org):
    """Suppliers with prices, ingredients, recipes in two contexts and one wedding package per person."""
    categories = {name: Category.objects.create(organization=org, name=name, order=i)
                  for i, name in enumerate(dict.fromkeys(row[1] for row in INGREDIENTS), 1)}
    suppliers = {name: Supplier.objects.create(organization=org, name=name, delivery_days=days) for name, days in SUPPLIERS.items()}
    ingredients = {}
    for name, category, base, supplier, price, unit, package in INGREDIENTS:
        ingredients[name] = Ingredient.objects.create(organization=org, name=name, category=categories[category], base_unit=base)
        SupplierPrice.objects.create(ingredient=ingredients[name], supplier=suppliers[supplier], price=D(price), unit=unit, package_size=D(package))
    contexts = {name: RecipeContext.objects.create(organization=org, name=name, target_fc_pct=D(fc)) for name, fc in CONTEXTS.items()}
    recipes = []
    for name, meal, ctx, price, rows in RECIPES:
        recipe = Recipe.objects.create(organization=org, name=name, meal_type=meal, yield_portions=D('1'), selling_price=D(price))
        recipe.contexts.set([contexts[c] for c in ctx])
        for order, (ing, qty, unit, yld) in enumerate(rows):
            RecipeIngredient.objects.create(recipe=recipe, ingredient=ingredients[ing], quantity=D(qty), unit=unit, yield_factor=D(yld), order=order)
        recipes.append(recipe)
    menu = Menu.objects.create(organization=org, name='Wesele — pakiet podstawowy', package_price_per_person=D('280.00'),
                               target_fc_pct=D('30.00'), notes='Przykład: rosół, danie główne i deser na osobę.')
    for order, recipe in enumerate([recipes[1], recipes[0], recipes[2]]):
        MenuItem.objects.create(menu=menu, recipe=recipe, quantity=D('1'), order=order)
    return org


# --- the visitor's sandbox ---------------------------------------------------------------------------------

class Unavailable(Exception):
    pass


def purge_expired():
    """Expired sandboxes go with their throwaway accounts and history rows (they were never a person's)."""
    for org in Organization.objects.filter(demo_until__lt=timezone.now()):
        purge(org)


def purge(org):
    pk = org.pk
    users = list(User.objects.filter(organization=org).values_list('pk', flat=True))
    # recipe lines and package dishes PROTECT their ingredient / recipe, even inside one cascade: they go first
    MenuItem.objects.filter(menu__organization=org).delete()
    RecipeIngredient.objects.filter(recipe__organization=org).delete()
    org.delete()  # ingredients, prices, recipes, menus, OCR reads go with it (CASCADE)
    User.objects.filter(pk__in=users).delete()
    for model in (Ingredient, Supplier, Recipe, Menu, User):
        model.history.filter(organization_id=pk).delete()
    Organization.history.filter(id=pk).delete()


@transaction.atomic
def start(request):
    purge_expired()
    now = timezone.now()
    if settings.DEMO_MAX <= 0:
        raise Unavailable('Demo jest wyłączone.')
    busy = Organization.objects.filter(demo_until__gt=now).count() >= settings.DEMO_MAX
    rush = Organization.objects.filter(demo_until__isnull=False, created_at__gt=now - timedelta(hours=1)).count() >= settings.DEMO_PER_HOUR
    if busy or rush:  # backpressure, not a queue
        raise Unavailable('Demo jest teraz oblegane — spróbuj za kilka minut.')
    tag = secrets.token_hex(4)
    org = fill(Organization.objects.create(name=NAME, slug=f'demo-{tag}', accepted_tos_at=now,
                                           demo_until=now + timedelta(hours=settings.DEMO_HOURS)))
    user = User.objects.create_user(username=f'demo-{tag}', email=f'demo-{tag}@demo.invalid', organization=org, role=User.ROLE_OWNER)
    user.set_unusable_password()
    user.save()
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return org
