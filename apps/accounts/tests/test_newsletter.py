"""Pole newslettera przy rejestracji: flaga, zapis po udanej rejestracji, błąd sieci nie psuje rejestracji."""
import json
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts import newsletter
from apps.accounts.models import User

DANE = {'email': 'nowy@example.test', 'password1': 'Local-Test-Password-123',
        'password2': 'Local-Test-Password-123', 'accept_tos': 'on'}


class NewsletterTests(TestCase):
    def register(self, wywolania, **extra):
        with mock.patch('apps.accounts.newsletter.zapisz', side_effect=lambda e, ip: wywolania.append((e, ip))):
            with self.captureOnCommitCallbacks(execute=True):
                return self.client.post(reverse('accounts:register'), {**DANE, **extra}, HTTP_X_FORWARDED_FOR='203.0.113.9')

    def test_bez_klucza_pola_nie_ma_i_nic_nie_wysylamy(self):
        self.assertNotContains(self.client.get(reverse('accounts:register')), 'name="newsletter"')
        wywolania = []
        self.assertRedirects(self.register(wywolania, newsletter='on'), reverse('accounts:setup'))
        self.assertEqual(wywolania, [])

    @override_settings(NEWSLETTER_KLUCZ='k')
    def test_z_kluczem_pole_jest_i_jest_niezaznaczone(self):
        html = self.client.get(reverse('accounts:register')).content.decode()
        self.assertIn('name="newsletter"', html)
        pole = html[html.index('name="newsletter"') - 200:html.index('name="newsletter"') + 120]
        self.assertNotIn('checked', pole)

    @override_settings(NEWSLETTER_KLUCZ='k')
    def test_zaznaczone_zapisuje_po_rejestracji_z_ip(self):
        wywolania = []
        self.assertRedirects(self.register(wywolania, newsletter='on'), reverse('accounts:setup'))
        self.assertEqual(wywolania, [('nowy@example.test', '203.0.113.9')])

    @override_settings(NEWSLETTER_KLUCZ='k')
    def test_niezaznaczone_nic_nie_wysyla(self):
        wywolania = []
        self.register(wywolania)
        self.assertEqual(wywolania, [])

    @override_settings(NEWSLETTER_KLUCZ='k')
    def test_nieudana_rejestracja_nic_nie_wysyla(self):
        wywolania = []
        response = self.register(wywolania, newsletter='on', accept_tos='')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(wywolania, [])
        self.assertFalse(User.objects.filter(email='nowy@example.test').exists())

    @override_settings(NEWSLETTER_KLUCZ='k', NEWSLETTER_URL='http://127.0.0.1:9/newsletter', NEWSLETTER_TIMEOUT=1)
    def test_blad_sieci_nie_psuje_rejestracji(self):
        with self.assertLogs('apps.accounts.newsletter', level='ERROR'):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(reverse('accounts:register'), {**DANE, 'newsletter': 'on'})
        self.assertRedirects(response, reverse('accounts:setup'))

    @override_settings(NEWSLETTER_KLUCZ='tajny', NEWSLETTER_URL='https://sudomie.pl/chat-api/newsletter')
    def test_zapytanie_do_sudomie_ma_klucz_email_i_ip(self):
        odpowiedz = mock.MagicMock(status=200)
        odpowiedz.__enter__.return_value = odpowiedz
        with mock.patch('urllib.request.urlopen', return_value=odpowiedz) as urlopen:
            self.assertTrue(newsletter.zapisz('ola@firma.pl', '83.1.2.3'))
        req = urlopen.call_args.args[0]
        self.assertEqual(req.get_header('X-newsletter-klucz'), 'tajny')
        self.assertEqual(json.loads(req.data), {'email': 'ola@firma.pl', 'ip': '83.1.2.3'})
