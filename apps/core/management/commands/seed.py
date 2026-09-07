from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import Organization, User
from apps.ingredients.models import Category, Ingredient, Supplier, SupplierPrice
from apps.recipes.models import Recipe, RecipeContext, RecipeIngredient

DEMO_EMAIL = 'demo@fc.sudomie.pl'
DEMO_PASSWORD = 'demo12345'


class Command(BaseCommand):
    help = 'Zasiewa organizację demo z przykładowymi składnikami, dostawcami i przepisami.'

    def handle(self, *args, **options):
        org, created = Organization.objects.get_or_create(
            slug='demo',
            defaults={'name': 'Restauracja Demo', 'accepted_tos_at': timezone.now()},
        )
        user, user_created = User.objects.get_or_create(
            email=DEMO_EMAIL,
            defaults={'username': DEMO_EMAIL, 'organization': org, 'role': User.ROLE_OWNER},
        )
        if user_created:
            user.set_password(DEMO_PASSWORD)
            user.save()

        warzywa = Category.objects.get_or_create(organization=org, name='Warzywa', defaults={'order': 1})[0]
        mieso = Category.objects.get_or_create(organization=org, name='Mięso', defaults={'order': 2})[0]
        nabial = Category.objects.get_or_create(organization=org, name='Nabiał', defaults={'order': 3})[0]

        makro = Supplier.objects.get_or_create(
            organization=org, name='Makro Cash&Carry',
            defaults={'delivery_days': 'Pon, Śr, Pt'},
        )[0]
        lokalny = Supplier.objects.get_or_create(
            organization=org, name='Lokalny dostawca warzyw',
            defaults={'delivery_days': 'Wt, Czw'},
        )[0]

        ingredients_data = [
            ('Ziemniaki', warzywa, 'kg', makro, Decimal('3.20'), 'kg', Decimal('1')),
            ('Cebula', warzywa, 'kg', makro, Decimal('2.80'), 'kg', Decimal('1')),
            ('Marchew', warzywa, 'kg', lokalny, Decimal('2.50'), 'kg', Decimal('1')),
            ('Pierś z kurczaka', mieso, 'kg', makro, Decimal('18.90'), 'kg', Decimal('1')),
            ('Schab wieprzowy', mieso, 'kg', makro, Decimal('22.50'), 'kg', Decimal('1')),
            ('Masło', nabial, 'kg', makro, Decimal('9.20'), 'kg', Decimal('1')),
            ('Śmietana 18%', nabial, 'l', makro, Decimal('7.80'), 'l', Decimal('1')),
            ('Mleko', nabial, 'l', makro, Decimal('3.10'), 'l', Decimal('1')),
            ('Mąka pszenna', warzywa, 'kg', makro, Decimal('4.00'), 'opak', Decimal('25')),
            ('Sól', warzywa, 'kg', makro, Decimal('1.50'), 'kg', Decimal('1')),
        ]

        ingredients = {}
        for name, category, base_unit, supplier, price, unit, package_size in ingredients_data:
            ingredient, _ = Ingredient.objects.get_or_create(
                organization=org, name=name,
                defaults={'category': category, 'base_unit': base_unit},
            )
            ingredients[name] = ingredient
            if not ingredient.prices.filter(supplier=supplier, is_current=True).exists():
                SupplierPrice.objects.create(
                    ingredient=ingredient, supplier=supplier, price=price,
                    unit=unit, package_size=package_size,
                )

        karta = RecipeContext.objects.get_or_create(
            organization=org, name='Karta', defaults={'target_fc_pct': Decimal('32.00')},
        )[0]
        bufet = RecipeContext.objects.get_or_create(
            organization=org, name='Bufet', defaults={'target_fc_pct': Decimal('28.00')},
        )[0]

        recipes_data = [
            ('Kotlet schabowy z ziemniakami', 'main', [karta], Decimal('1'), Decimal('32.00'), [
                ('Schab wieprzowy', Decimal('0.18'), 'kg', Decimal('0.90')),
                ('Ziemniaki', Decimal('0.25'), 'kg', Decimal('1.00')),
                ('Mąka pszenna', Decimal('0.02'), 'kg', Decimal('1.00')),
            ]),
            ('Rosół z kurczaka', 'soup', [karta, bufet], Decimal('1'), Decimal('14.00'), [
                ('Pierś z kurczaka', Decimal('0.12'), 'kg', Decimal('0.85')),
                ('Marchew', Decimal('0.05'), 'kg', Decimal('0.90')),
                ('Cebula', Decimal('0.03'), 'kg', Decimal('0.90')),
            ]),
            ('Naleśniki ze śmietaną', 'dessert', [bufet], Decimal('1'), Decimal('12.00'), [
                ('Mleko', Decimal('0.15'), 'l', Decimal('1.00')),
                ('Mąka pszenna', Decimal('0.08'), 'kg', Decimal('1.00')),
                ('Śmietana 18%', Decimal('0.05'), 'l', Decimal('1.00')),
                ('Masło', Decimal('0.01'), 'kg', Decimal('1.00')),
            ]),
        ]

        for name, meal_type, contexts, yield_portions, selling_price, rows in recipes_data:
            recipe, recipe_created = Recipe.objects.get_or_create(
                organization=org, name=name,
                defaults={
                    'meal_type': meal_type, 'yield_portions': yield_portions,
                    'selling_price': selling_price,
                },
            )
            if recipe_created:
                recipe.contexts.set(contexts)
                for order, (ing_name, quantity, unit, yield_factor) in enumerate(rows):
                    RecipeIngredient.objects.create(
                        recipe=recipe, ingredient=ingredients[ing_name],
                        quantity=quantity, unit=unit, yield_factor=yield_factor, order=order,
                    )

        self.stdout.write(self.style.SUCCESS(
            f'Zasiano organizację "{org.name}". Zaloguj się: {DEMO_EMAIL} / {DEMO_PASSWORD}',
        ))
