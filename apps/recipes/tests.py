from decimal import Decimal as D
from django.test import TestCase
from django.urls import reverse
from apps.accounts.models import Organization, User
from apps.ingredients.forms import SupplierPriceForm
from apps.ingredients.models import Ingredient, Supplier, SupplierPrice
from apps.recipes.models import Menu, MenuItem, Recipe, RecipeIngredient


class CostCompletenessTests(TestCase):
    """Brak ceny / niezgodna jednostka / puste menu nie mogą wyglądać na kompletny koszt."""

    def setUp(self):
        self.org = Organization.objects.create(name='A', slug='a')
        self.user = User.objects.create_user(username='u', organization=self.org, role='owner')
        self.client.force_login(self.user)
        self.sup = Supplier.objects.create(organization=self.org, name='S')
        self.ing = Ingredient.objects.create(organization=self.org, name='Schab', base_unit='kg')

    def dish(self, qty='0.2', unit='kg', ing=None, **kw):
        r = Recipe.objects.create(organization=self.org, name='Danie', **kw)
        RecipeIngredient.objects.create(recipe=r, ingredient=ing or self.ing, quantity=D(qty), unit=unit)
        return r

    def menu(self, *recipes, qty='1', pkg='60'):
        m = Menu.objects.create(organization=self.org, name='Pakiet', package_price_per_person=D(pkg))
        for r in recipes:
            MenuItem.objects.create(menu=m, recipe=r, quantity=D(qty))
        return m

    def price(self, p='20', unit='kg', ing=None, **kw):
        return SupplierPrice.objects.create(ingredient=ing or self.ing, supplier=self.sup, price=D(p), unit=unit, **kw)

    def test_complete_reference_scenario(self):
        m = self.menu(self.dish(), qty='1.5'); self.price()
        self.assertTrue(m.is_cost_complete)
        self.assertEqual((m.total_cost_per_person, m.food_cost_pct), (D('6.00'), D('10.0')))
        self.price('25')
        self.assertEqual((m.total_cost_per_person, m.food_cost_pct), (D('7.50'), D('12.5')))

    def test_empty_menu_incomplete_no_fc(self):
        m = self.menu()
        self.assertFalse(m.is_cost_complete)
        self.assertIsNone(m.food_cost_pct)
        self.assertEqual(m.fc_status, 'unknown')

    def test_empty_recipe_incomplete(self):
        r = Recipe.objects.create(organization=self.org, name='Puste')
        self.assertFalse(r.is_cost_complete)
        self.assertFalse(self.menu(r).is_cost_complete)

    def test_unpriced_ingredient_incomplete_no_fc(self):
        m = self.menu(self.dish())
        self.assertFalse(m.is_cost_complete)
        self.assertIsNone(m.food_cost_pct)
        html = self.client.get(reverse('recipes:menu-detail', args=[m.pk])).content.decode()
        self.assertIn('Koszt tego menu jest niepełny', html)
        self.assertNotIn('fc-ok', html)

    def test_partially_priced_incomplete(self):
        other = Ingredient.objects.create(organization=self.org, name='Ziemniak', base_unit='kg')
        r = self.dish(); RecipeIngredient.objects.create(recipe=r, ingredient=other, quantity=D('0.3'), unit='kg')
        self.price()
        m = self.menu(r)
        self.assertFalse(m.is_cost_complete)
        self.assertIsNone(m.food_cost_pct)

    def test_incompatible_recipe_unit_incomplete(self):
        self.price()
        for unit in ('l', 'szt'):
            self.assertFalse(self.menu(self.dish(unit=unit)).is_cost_complete, unit)

    def test_incompatible_price_unit_ignored(self):
        self.price('8', unit='szt')          # 8 zł/szt dla składnika w kg
        self.price('100', unit='opak')       # opak bez rozmiaru
        self.assertIsNone(self.ing.get_best_price())
        self.assertFalse(self.menu(self.dish()).is_cost_complete)
        self.price('500', unit='opak', package_size=D('25'))
        self.assertEqual(self.ing.get_best_price(), D('20'))

    def test_zero_yield_or_quantity_incomplete(self):
        self.price()
        r = self.dish(); ri = r.recipe_ingredients.get()
        RecipeIngredient.objects.filter(pk=ri.pk).update(yield_factor=D('0'))
        self.assertFalse(r.is_cost_complete)

    def test_manual_cost_incl_explicit_zero_complete(self):
        self.assertTrue(self.menu(Recipe.objects.create(organization=self.org, name='R', manual_cost_override=D('0'))).is_cost_complete)

    def test_price_form_rejects_incompatible_unit(self):
        form = SupplierPriceForm(self.org, {'supplier': self.sup.pk, 'price': '8', 'unit': 'szt', 'is_netto': 'on'},
                                 instance=SupplierPrice(ingredient=self.ing))
        self.assertFalse(form.is_valid())
        ok = SupplierPriceForm(self.org, {'supplier': self.sup.pk, 'price': '8', 'unit': 'g', 'is_netto': 'on'},
                               instance=SupplierPrice(ingredient=self.ing))
        self.assertTrue(ok.is_valid(), ok.errors)

    def test_invoice_confirm_skips_incompatible_unit(self):
        s = self.client.session
        s['invoice_items'] = [{'name': 'Schab', 'price': '8', 'unit': 'szt'}]; s['invoice_meta'] = {}; s.save()
        r = self.client.post(reverse('ingredients:invoice-confirm'), {
            'supplier_choice': self.sup.pk, 'save_0': '1', 'ingredient_id_0': self.ing.pk,
            'price_0': '8', 'unit_0': 'szt', 'is_netto_0': '1'}, follow=True)
        self.assertContains(r, 'Pominięto: 1')
        self.assertFalse(SupplierPrice.objects.exists())

    def test_offer_and_menu_agree_on_complete(self):
        from apps.offers.views import snapshot_line
        from apps.offers.models import OfferLine
        m = self.menu(self.dish())
        line = OfferLine(menu=m); snapshot_line(line, None, False)
        self.assertEqual(line.cost_complete, m.is_cost_complete)
        self.price(); snapshot_line(line, m.pk, True)
        self.assertEqual((line.cost_complete, m.is_cost_complete), (True, True))
