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
        self.assertEqual(Recipe.objects.filter(organization=org_a).count(), 3)
        menu = Menu.objects.get(organization=org_a)
        self.assertEqual(menu.items.count(), 3)
        page = a.get('/')
        self.assertContains(page, 'Twoja własna restauracja przykładowa')
        self.assertContains(page, '/demo/koniec/')
        other = Recipe.objects.filter(organization=org_b).first()
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

    def test_seed_is_idempotent_and_has_no_password_in_code(self):
        with mock.patch.dict('os.environ', {'DEMO_PASSWORD': 'a-long-local-demo-password'}):
            call_command('seed', stdout=open('/dev/null', 'w'))
            call_command('seed', stdout=open('/dev/null', 'w'))
        user = User.objects.get(email='demo@fc.sudomie.pl')
        self.assertFalse(user.check_password('demo12345'))
        self.assertTrue(user.check_password('a-long-local-demo-password'))
        self.assertEqual(Organization.objects.filter(slug='demo').count(), 1)
