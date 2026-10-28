"""Restauracja Demo. One builder for `manage.py seed` (a fixed demo on a server) and for the sandbox every visitor gets
from „Wypróbuj demo”: an own copy, an account without a password (only this session enters it), erased after DEMO_HOURS.
Invoice OCR stays off in a sandbox — every read costs money at OpenAI (Organization.ocr_available, ocr_access)."""

import json
import secrets
from datetime import timedelta
from decimal import Decimal as D
from pathlib import Path

from django.conf import settings
from django.contrib.auth import login
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Organization, User
from apps.ingredients.models import Category, Ingredient, Supplier, SupplierPrice
from apps.offers.models import Offer, OfferLine
from apps.recipes.models import Menu, MenuItem, Recipe, RecipeContext, RecipeIngredient

DATA = Path(__file__).resolve().parent / 'data' / 'demo.json'  # the content lives in data, not in code (CLAUDE.md)


def data():
    return json.loads(DATA.read_text(encoding='utf-8'))


NAME = data()['name']


def sample_invoice():
    """The demo invoice as OCR would return it (data/demo-faktura.json), dated today — no call to OpenAI."""
    raw = json.loads((DATA.parent / 'demo-faktura.json').read_text(encoding='utf-8'))
    raw['invoice_date'] = timezone.localdate().isoformat()
    return raw


def fill(org):
    """Suppliers, ingredients with a price history (the last price is current), recipes in contexts and packages
    per person — all from data/demo.json. An ingredient without prices stays without: the incomplete-cost warning."""
    d, now = data(), timezone.now()
    suppliers = {s['name']: Supplier.objects.create(organization=org, name=s['name'], delivery_days=s['delivery_days'])
                 for s in d['suppliers']}
    categories = {name: Category.objects.create(organization=org, name=name, order=i)
                  for i, name in enumerate(dict.fromkeys(row['category'] for row in d['ingredients']), 1)}
    ingredients = {}
    for row in d['ingredients']:
        ingredient = Ingredient.objects.create(organization=org, name=row['name'], category=categories[row['category']],
                                               base_unit=row['base_unit'])
        ingredients[row['name']] = ingredient
        for days_ago, price in row['prices']:  # oldest first: each save archives the previous current price
            sp = SupplierPrice.objects.create(ingredient=ingredient, supplier=suppliers[row['supplier']], price=D(price),
                                              unit=row['unit'], package_size=D(row['package_size']))
            SupplierPrice.objects.filter(pk=sp.pk).update(valid_from=now - timedelta(days=days_ago))
    contexts = {c['name']: RecipeContext.objects.create(organization=org, name=c['name'], target_fc_pct=D(c['target_fc_pct']))
                for c in d['contexts']}
    recipes = {}
    for row in d['recipes']:
        recipe = Recipe.objects.create(organization=org, name=row['name'], meal_type=row['meal_type'], yield_portions=D('1'),
                                       selling_price=D(row['selling_price']))
        recipe.contexts.set([contexts[c] for c in row['contexts']])
        for order, (ing, qty, unit, yld) in enumerate(row['items']):
            RecipeIngredient.objects.create(recipe=recipe, ingredient=ingredients[ing], quantity=D(qty), unit=unit,
                                            yield_factor=D(yld), order=order)
        recipes[row['name']] = recipe
    for row in d['menus']:
        menu = Menu.objects.create(organization=org, name=row['name'], package_price_per_person=D(row['package_price_per_person']),
                                   target_fc_pct=D(row['target_fc_pct']), notes=row['notes'])
        for order, (name, qty) in enumerate(row['items']):
            MenuItem.objects.create(menu=menu, recipe=recipes[name], quantity=D(qty), order=order)
    menus = {m.name: m for m in Menu.objects.filter(organization=org)}
    today = timezone.localdate()
    for row in d.get('offers', []):
        offer = Offer.objects.create(
            organization=org, seller_name=org.name, seller_details=row['seller_details'], title=row['title'],
            client_name=row['client_name'], client_details=row['client_details'], persons=row['persons'],
            date_from=today + timedelta(days=row['in_days']), date_to=today + timedelta(days=row['in_days']),
            valid_until=today + timedelta(days=row['valid_days']), status=row['status'], deposit_pct=D(row['deposit_pct']),
            terms=row['terms'], internal_notes=row['internal_notes'])
        for order, line in enumerate(row['lines']):
            menu = menus.get(line.get('menu'))
            OfferLine.objects.create(  # cost snapshot as the panel takes it (offers.views)
                offer=offer, kind=line['kind'], menu=menu, description=line['description'], details=line['details'],
                quantity=D(line['quantity']), unit=line['unit'], unit_price=D(line['unit_price']), order=order,
                cost_per_unit=menu.total_cost_per_person if menu else None, cost_complete=bool(menu and menu.is_cost_complete))
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
