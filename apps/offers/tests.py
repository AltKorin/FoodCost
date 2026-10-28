from datetime import date
from decimal import Decimal
from django.test import TestCase, override_settings
from django.urls import reverse
from apps.accounts.models import Organization, User
from apps.recipes.models import Menu, MenuItem, Recipe
from .models import Offer


@override_settings(OFFERS_ENABLED=True)
class OfferTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='A', slug='a')
        self.other = Organization.objects.create(name='B', slug='b')
        self.user = User.objects.create_user(username='owner', organization=self.org, role='owner')
        self.client.force_login(self.user)
        self.recipe = Recipe.objects.create(organization=self.org, name='Zupa', manual_cost_override=12)
        self.menu = Menu.objects.create(organization=self.org, name='Lunch', package_price_per_person=60)
        MenuItem.objects.create(menu=self.menu, recipe=self.recipe)
        self.foreign_menu = Menu.objects.create(organization=self.other, name='Tajne', package_price_per_person=10)

    def data(self, **overrides):
        data = {'title':'Spotkanie', 'client_name':'Klient', 'seller_name':'A', 'date_from':'2026-10-10', 'date_to':'2026-10-11', 'persons':'10', 'deposit_pct':'30', 'status':'draft', 'lines-TOTAL_FORMS':'1', 'lines-INITIAL_FORMS':'0', 'lines-MIN_NUM_FORMS':'1', 'lines-MAX_NUM_FORMS':'100', 'lines-0-kind':'menu', 'lines-0-menu':self.menu.pk, 'lines-0-quantity':'10', 'lines-0-unit':'os.', 'lines-0-unit_price':''}
        data.update(overrides)
        return data

    def create(self):
        self.assertEqual(self.client.post(reverse('offers:create'), self.data()).status_code, 302)
        return Offer.objects.get()

    def test_totals_and_customer_document(self):
        offer = self.create()
        self.assertEqual(offer.total, Decimal('600'))
        self.assertEqual(offer.deposit, Decimal('180'))
        self.assertEqual(offer.gastronomy_cost, Decimal('120'))
        self.assertEqual(offer.food_cost_pct, Decimal('20'))
        offer.internal_notes = 'SECRET-INTERNAL'
        offer.save()
        for name in ['detail', 'edit', 'print']:
            self.assertEqual(self.client.get(reverse('offers:'+name, args=[offer.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('offers:list')).status_code, 200)
        response = self.client.get(reverse('offers:print', args=[offer.pk]))
        self.assertNotContains(response, 'SECRET-INTERNAL')
        self.assertNotContains(response, 'Food cost')
        self.assertContains(response, 'Zupa')

    def test_tenant_isolation(self):
        response = self.client.post(reverse('offers:create'), self.data(**{'lines-0-menu':self.foreign_menu.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Offer.objects.exists())
        foreign = Offer.objects.create(organization=self.other, seller_name='B', title='SECRET', client_name='B', date_from=date.today(), date_to=date.today(), persons=1)
        for name in ['detail', 'edit', 'print']:
            self.assertEqual(self.client.get(reverse('offers:'+name, args=[foreign.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('offers:list')), 'SECRET')

    def test_snapshot_and_explicit_refresh(self):
        offer = self.create()
        line = offer.lines.get()
        self.recipe.name = 'Nowa zupa'
        self.recipe.manual_cost_override = 20
        self.recipe.save()
        self.menu.package_price_per_person = 90
        self.menu.save()
        data = self.data(**{'revision':offer.revision, 'lines-INITIAL_FORMS':'1', 'lines-0-id':line.pk, 'lines-0-description':line.description, 'lines-0-details':line.details, 'lines-0-unit_price':'60', 'title':'Inny tytuł'})
        self.assertEqual(self.client.post(reverse('offers:edit', args=[offer.pk]), data).status_code, 302)
        line.refresh_from_db()
        self.assertEqual(line.cost_per_unit, Decimal('12'))
        self.assertEqual(line.details, 'Zupa')
        offer.refresh_from_db()
        data['revision'] = offer.revision
        data['lines-0-refresh_menu'] = 'on'
        self.assertEqual(self.client.post(reverse('offers:edit', args=[offer.pk]), data).status_code, 302)
        line.refresh_from_db()
        self.assertEqual(line.cost_per_unit, Decimal('20'))
        self.assertEqual(line.details, 'Nowa zupa')
        self.assertEqual(line.unit_price, Decimal('60'))

    def test_stale_revision_and_read_only_role(self):
        offer = self.create()
        data = self.data(**{'revision':'0', 'lines-INITIAL_FORMS':'1', 'lines-0-id':offer.lines.get().pk, 'title':'Nadpisane'})
        self.assertContains(self.client.post(reverse('offers:edit', args=[offer.pk]), data), 'Oferta została zmieniona')
        offer.refresh_from_db()
        self.assertEqual(offer.title, 'Spotkanie')
        self.user.role = 'viewer'
        self.user.save()
        self.assertEqual(self.client.post(reverse('offers:create'), self.data()).status_code, 403)

    def test_manual_menu_cost_unknown_and_invalid_inputs(self):
        data = self.data(**{'lines-0-menu':'', 'lines-0-description':'Bufet', 'lines-0-unit_price':'100'})
        self.assertEqual(self.client.post(reverse('offers:create'), data).status_code, 302)
        offer = Offer.objects.get()
        self.assertFalse(offer.cost_complete)
        self.assertIsNone(offer.food_cost_pct)
        data.update({'date_to':'2026-10-01', 'deposit_pct':'101', 'lines-0-unit_price':'-1'})
        self.assertEqual(self.client.post(reverse('offers:create'), data).status_code, 200)
        self.assertEqual(Offer.objects.count(), 1)

    def test_login_and_setup_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('offers:list')).status_code, 302)
        self.user.organization = None
        self.user.save()
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(reverse('offers:list')), reverse('accounts:setup'))

    def test_room_and_service_totals_and_zero_price(self):
        data = self.data(**{'lines-TOTAL_FORMS':'3', 'lines-0-unit_price':'0', 'lines-1-kind':'room', 'lines-1-description':'Pokój × noce', 'lines-1-quantity':'6', 'lines-1-unit':'pokój/noc', 'lines-1-unit_price':'200', 'lines-2-kind':'service', 'lines-2-description':'Sala', 'lines-2-quantity':'1', 'lines-2-unit':'dzień', 'lines-2-unit_price':'300'})
        self.assertEqual(self.client.post(reverse('offers:create'), data).status_code, 302)
        offer = Offer.objects.get()
        self.assertEqual(offer.total, Decimal('1500'))
        self.assertEqual(offer.gastronomy_total, Decimal('0'))
        self.assertIsNone(offer.food_cost_pct)

    def test_empty_menu_has_unknown_cost(self):
        data = self.data(**{'lines-0-menu':Menu.objects.create(organization=self.org, name='Puste', package_price_per_person=50).pk})
        self.assertEqual(self.client.post(reverse('offers:create'), data).status_code, 302)
        self.assertFalse(Offer.objects.get().cost_complete)


class OffersFlagTests(TestCase):
    def test_switched_off_offers_answer_404_even_when_logged_in(self):
        from apps.accounts.models import Organization, User
        org = Organization.objects.create(name='Lokal', slug='lokal-flag')
        user = User.objects.create_user(username='flag@example.test', email='flag@example.test', password='x-long-password-1', organization=org, role=User.ROLE_OWNER)
        self.client.force_login(user)
        with override_settings(OFFERS_ENABLED=False):
            self.assertEqual(self.client.get('/offers/').status_code, 404)
            self.assertNotContains(self.client.get('/', follow=True), '/offers/')
        with override_settings(OFFERS_ENABLED=True):
            self.assertEqual(self.client.get('/offers/').status_code, 200)
