"""„Wypróbuj demo” (apps.core.demo): every visitor gets an own restaurant; it disappears; invoice OCR never runs there."""
import uuid
from datetime import timedelta
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from apps.accounts import ocr_access
from apps.accounts.models import Organization, User
from apps.core import demo
from apps.ingredients.models import Ingredient, SupplierPrice
from apps.recipes.models import Menu, Recipe


@override_settings(DEMO_MAX=3, DEMO_HOURS=24, DEMO_PER_HOUR=10)
class SandboxDemoTests(TestCase):
    def visitor(self):
        client = Client()
        response = client.post('/demo/')
        self.assertRedirects(response, '/', fetch_redirect_response=False)
        user = User.objects.get(pk=client.session['_auth_user_id'])
        return client, user.organization

    def test_visitor_gets_own_restaurant_with_data_and_a_wedding_package(self):
        a, org_a = self.visitor()
        b, org_b = self.visitor()
        self.assertNotEqual(org_a.pk, org_b.pk)
        data = demo.data()
        self.assertEqual(Recipe.objects.filter(organization=org_a).count(), len(data['recipes']))
        self.assertEqual(Menu.objects.filter(organization=org_a).count(), len(data['menus']))
        page = a.get('/')
        self.assertContains(page, 'Twoja własna restauracja przykładowa')
        self.assertContains(page, '/demo/koniec/')
        other = Recipe.objects.filter(organization=org_b).first()  # noqa: the other visitor's recipe
        self.assertEqual(a.get(f'/recipes/{other.pk}/').status_code, 404)  # the other visitor's data

    def test_no_password_and_no_invoice_ocr(self):
        client, org = self.visitor()
        user = User.objects.get(organization=org)
        self.assertFalse(user.has_usable_password())
        self.assertFalse(org.ocr_available)
        with self.assertRaisesMessage(ValueError, 'W demo odczyt faktur jest wyłączony'):
            ocr_access.reserve_read(org.pk, 1, uuid.uuid4())
        with mock.patch('apps.ingredients.ocr_service.extract_invoice_data') as extract:
            client.post('/ingredients/invoice/upload/', {})
            extract.assert_not_called()

    def test_limits_csrf_and_switch_off(self):
        for _ in range(3):
            self.visitor()
        self.assertEqual(Client().post('/demo/').status_code, 503)  # DEMO_MAX
        self.assertEqual(Client(enforce_csrf_checks=True).post('/demo/').status_code, 403)
        self.assertEqual(Client().get('/demo/').status_code, 405)
        with override_settings(DEMO_MAX=0):
            self.assertEqual(Client().post('/demo/').status_code, 503)
            self.assertNotContains(Client().get('/'), 'Wypróbuj demo')
        with override_settings(DEMO_MAX=100, DEMO_PER_HOUR=3):
            self.assertEqual(Client().post('/demo/').status_code, 503)  # 3 started in the last hour

    def test_expired_sandbox_disappears_with_accounts_and_history(self):
        _, org = self.visitor()
        pk, users = org.pk, User.objects.count()
        later = timezone.now() + timedelta(hours=25)
        with mock.patch('django.utils.timezone.now', return_value=later):
            self.visitor()  # starting a new one sweeps the expired ones
        self.assertFalse(Organization.objects.filter(pk=pk).exists())
        self.assertEqual(User.objects.count(), users)  # one gone, one new
        self.assertFalse(Organization.history.filter(id=pk).exists())
        self.assertFalse(Recipe.history.filter(organization_id=pk).exists())

    def test_leaving_the_demo_goes_to_registration(self):
        client, _ = self.visitor()
        self.assertRedirects(client.get('/demo/koniec/'), '/register/', fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', client.session)


class SeedTests(TestCase):
    @override_settings(DEBUG=False)
    def test_seed_needs_its_own_password_on_a_server(self):
        with mock.patch.dict('os.environ', {'DEMO_PASSWORD': ''}), self.assertRaises(CommandError):
            call_command('seed')
        self.assertFalse(Organization.objects.exists())

    def test_data_shows_a_price_rise_and_an_incomplete_package(self):
        org = demo.fill(Organization.objects.create(name='X', slug='x'))
        schab = Ingredient.objects.get(organization=org, name='Schab wieprzowy')
        history = list(SupplierPrice.objects.filter(ingredient=schab).order_by('valid_from'))
        self.assertEqual([str(p.price) for p in history], ['19.90', '21.20', '22.50'])
        self.assertEqual([p.is_current for p in history], [False, False, True])
        self.assertGreater((timezone.now() - history[0].valid_from).days, 100)
        menus = {m.name: m for m in Menu.objects.filter(organization=org)}
        self.assertTrue(menus['Obiad weselny — podstawowy'].is_cost_complete)
        self.assertFalse(menus['Obiad komunijny'].is_cost_complete)  # koperek has no price: the warning to show
        from apps.offers.models import Offer
        wedding = Offer.objects.get(organization=org, title='Wesele Anny i Piotra')
        self.assertTrue(wedding.cost_complete)
        self.assertGreater(wedding.total, wedding.gastronomy_total)  # rooms and services on top of the food
        self.assertFalse(Offer.objects.get(organization=org, title='Komunia Zosi').cost_complete)
        basic, premium = menus['Obiad weselny — podstawowy'], menus['Obiad weselny — premium']
        self.assertLess(abs(basic.food_cost_pct - basic.target_fc_pct), 3)  # a believable result on target
        self.assertGreater(premium.food_cost_pct, premium.target_fc_pct)  # and one above it, to show the alert

    def test_reset_gives_a_clean_presentation_and_spares_sandboxes(self):
        with mock.patch.dict('os.environ', {'DEMO_PASSWORD': 'a-long-local-demo-password'}):
            call_command('seed', stdout=open('/dev/null', 'w'))
            org = Organization.objects.get(slug='demo')
            Ingredient.objects.filter(organization=org, name='Sól').update(name='Zmienione na pokazie')
            sandbox = demo.fill(Organization.objects.create(name='Gość', slug='demo-abc', demo_until=timezone.now() + timedelta(hours=1)))
            call_command('seed', '--reset', stdout=open('/dev/null', 'w'))
        fresh = Organization.objects.get(slug='demo')
        self.assertTrue(Ingredient.objects.filter(organization=fresh, name='Sól').exists())
        self.assertFalse(Ingredient.objects.filter(name='Zmienione na pokazie').exists())
        self.assertTrue(Organization.objects.filter(pk=sandbox.pk).exists())
        self.assertTrue(User.objects.get(email='demo@fc.sudomie.pl').check_password('a-long-local-demo-password'))

    def test_seed_is_idempotent_and_has_no_password_in_code(self):
        with mock.patch.dict('os.environ', {'DEMO_PASSWORD': 'a-long-local-demo-password'}):
            call_command('seed', stdout=open('/dev/null', 'w'))
            call_command('seed', stdout=open('/dev/null', 'w'))
        user = User.objects.get(email='demo@fc.sudomie.pl')
        self.assertFalse(user.check_password('demo12345'))
        self.assertTrue(user.check_password('a-long-local-demo-password'))
        self.assertEqual(Organization.objects.filter(slug='demo').count(), 1)


@override_settings(DEMO_MAX=3, DEMO_HOURS=24, DEMO_PER_HOUR=10)
class SampleInvoiceTests(TestCase):
    """„Odczytaj przykładową fakturę”: the real matching and confirm step, without OCR — and only in a demo."""

    def setUp(self):
        self.client = Client()
        self.client.post('/demo/')
        self.org = User.objects.get(pk=self.client.session['_auth_user_id']).organization

    def test_sample_goes_through_matching_without_openai_and_completes_the_package(self):
        with mock.patch('apps.ingredients.ocr_service._call_openai_vision') as openai:
            self.assertContains(self.client.get('/ingredients/invoice/upload/'), 'Odczytaj przykładową fakturę')
            self.assertRedirects(self.client.post('/ingredients/invoice/sample/'), '/ingredients/invoice/confirm/', fetch_redirect_response=False)
            openai.assert_not_called()
        items = self.client.session['invoice_items']
        matched = {i['name']: i['matched_ingredient_name'] for i in items}
        self.assertEqual(matched['Dorsz filet mrożony'], 'Dorsz — filet')
        self.assertEqual(matched['Koperek pęczek'], 'Koperek')
        self.assertIsNone(matched['Pieprz czarny mielony'])  # the „utwórz nowy składnik” case
        self.assertIsNotNone(self.client.session['invoice_supplier_id'])
        page = self.client.get('/ingredients/invoice/confirm/')
        self.assertContains(page, 'Przykładowa faktura')
        form = {'supplier_choice': str(self.client.session['invoice_supplier_id'])}
        for n, item in enumerate(items):
            form.update({f'save_{n}': 'on', f'price_{n}': item['price'], f'unit_{n}': item['unit'],
                         f'package_size_{n}': item['package_size'] or '', f'is_netto_{n}': '1',
                         f'ingredient_id_{n}': str(item['matched_ingredient_id'] or '__new__')})
        premium = Menu.objects.get(organization=self.org, name='Obiad weselny — premium')
        before = premium.total_cost_per_person
        self.client.post('/ingredients/invoice/confirm/', form)
        self.assertGreater(Menu.objects.get(pk=premium.pk).total_cost_per_person, before)  # the package cost rose
        cod = Ingredient.objects.get(organization=self.org, name='Dorsz — filet')
        self.assertEqual(str(cod.get_current_prices().first().price), '52.90')  # same supplier: the rise replaces the price
        self.assertTrue(Ingredient.objects.filter(organization=self.org, name='Pieprz czarny mielony').exists())
        self.assertTrue(Menu.objects.get(organization=self.org, name='Obiad komunijny').is_cost_complete)  # koperek now has a price

    def test_a_real_restaurant_gets_no_sample(self):
        org = Organization.objects.create(name='Prawdziwa', slug='prawdziwa')
        user = User.objects.create_user(username='szef@example.test', email='szef@example.test', password='x-long-password-1',
                                        organization=org, role=User.ROLE_OWNER)
        client = Client()
        client.force_login(user)
        self.assertEqual(client.post('/ingredients/invoice/sample/').status_code, 404)
        self.assertNotContains(client.get('/ingredients/invoice/upload/'), 'Odczytaj przykładową fakturę')
        self.assertEqual(Client().post('/ingredients/invoice/sample/').status_code, 302)  # anonymous → login
