import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

import fitz
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, close_old_connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from apps.accounts.models import Organization, User, OCRRead
from apps.accounts.ocr_access import reserve_read, finish_read


def organization(slug='test'):
    return Organization.objects.create(name=slug, slug=slug)


def photo():
    data = BytesIO()
    Image.new('RGB', (100, 100), 'white').save(data, format='PNG')
    return SimpleUploadedFile('invoice.png', data.getvalue(), content_type='image/png')


def pdf(pages):
    with fitz.open() as doc:
        for _ in range(pages):
            doc.new_page()
        return SimpleUploadedFile('invoice.pdf', doc.tobytes(), content_type='application/pdf')


INVOICE = {'supplier_name': 'Test', 'invoice_number': '1', 'invoice_date': None, 'warnings': [], 'items': [
    {'name': 'Maka 5kg', 'price': 20, 'quantity': 5, 'purchased_quantity': 3,
     'unit': 'kg', 'price_type': 'za_opakowanie', 'is_netto': True, 'vat': 5}
]}


class TrialAccountingTests(TestCase):
    def setUp(self):
        self.org = organization()

    def test_first_success_starts_trial_and_counts_pages(self):
        read = reserve_read(self.org.pk, 3, uuid.uuid4())
        self.org.refresh_from_db()
        self.assertIsNone(self.org.ocr_trial_started_at)
        finish_read(read, success=True)
        self.org.refresh_from_db()
        self.assertEqual(self.org.ocr_trial_pages_left, 27)
        self.assertEqual(self.org.ocr_trial_days_left, 30)
        self.assertIsNotNone(self.org.ocr_trial_started_at)

    def test_failure_does_not_start_or_charge(self):
        read = reserve_read(self.org.pk, 10, uuid.uuid4())
        finish_read(read, success=False)
        self.org.refresh_from_db()
        self.assertEqual(self.org.ocr_trial_pages_left, 30)
        self.assertIsNone(self.org.ocr_trial_started_at)

    def test_reservations_prevent_exceeding_limit(self):
        self.org.ocr_trial_pages_used = 25
        self.org.save()
        read = reserve_read(self.org.pk, 5, uuid.uuid4())
        with self.assertRaises(ValueError):
            reserve_read(self.org.pk, 1, uuid.uuid4())
        finish_read(read, success=True)
        self.org.refresh_from_db()
        self.assertFalse(self.org.ocr_available)
        with self.assertRaises(ValueError):
            reserve_read(self.org.pk, 1, uuid.uuid4())

    def test_trial_exactly_30_days_and_no_reset(self):
        start = timezone.now() - timedelta(days=29)
        self.org.ocr_trial_started_at = start
        self.org.save()
        finish_read(reserve_read(self.org.pk, 1, uuid.uuid4()), success=True)
        self.org.refresh_from_db()
        self.assertEqual(self.org.ocr_trial_started_at, start)
        with patch('django.utils.timezone.now', return_value=start + timedelta(days=30)):
            self.assertEqual(self.org.ocr_trial_days_left, 0)
            with self.assertRaises(ValueError):
                reserve_read(self.org.pk, 1, uuid.uuid4())

    def test_duplicate_request_and_completion_do_not_charge_twice(self):
        token = uuid.uuid4()
        read = reserve_read(self.org.pk, 1, token)
        with self.assertRaises(ValueError):
            reserve_read(self.org.pk, 1, token)
        finish_read(read, success=True)
        with self.assertRaises(ValueError):
            finish_read(read, success=True)
        self.org.refresh_from_db()
        self.assertEqual(self.org.ocr_trial_pages_used, 1)

    def test_stale_reservation_is_released(self):
        self.org.ocr_trial_pages_used = 20
        self.org.save()
        read = reserve_read(self.org.pk, 10, uuid.uuid4())
        OCRRead.objects.filter(pk=read.pk).update(created_at=timezone.now() - timedelta(minutes=6))
        reserve_read(self.org.pk, 10, uuid.uuid4())
        read.refresh_from_db()
        self.assertEqual(read.status, 'failed')

    def test_existing_pro_keeps_access(self):
        self.org.plan = Organization.PLAN_PRO
        self.org.ocr_trial_pages_used = 30
        self.org.ocr_trial_started_at = timezone.now() - timedelta(days=40)
        self.org.save()
        finish_read(reserve_read(self.org.pk, 10, uuid.uuid4()), success=True)
        self.org.refresh_from_db()
        self.assertEqual(self.org.ocr_trial_pages_used, 30)
        self.assertTrue(self.org.ocr_available)

    def test_organizations_have_separate_limits(self):
        self.org.ocr_trial_pages_used = 30
        self.org.save()
        other = organization('other')
        finish_read(reserve_read(other.pk, 1, uuid.uuid4()), success=True)
        other.refresh_from_db()
        self.assertEqual(other.ocr_trial_pages_used, 1)


class TrialViewsTests(TestCase):
    def setUp(self):
        self.org = organization()
        self.user = User.objects.create_user(username='trial@example.test', email='trial@example.test', password='local-test-password', organization=self.org, role=User.ROLE_OWNER)
        self.client.force_login(self.user)

    def test_get_and_estimate_do_not_start_trial_or_call_api(self):
        self.assertEqual(self.client.get(reverse('ingredients:invoice-upload')).status_code, 200)
        with patch('apps.ingredients.invoice_views.extract_invoice_data') as api:
            response = self.client.post(reverse('ingredients:invoice-estimate'), {'invoice_file': pdf(3)})
        api.assert_not_called()
        self.assertEqual(response.json()['pages'], 3)
        self.org.refresh_from_db()
        self.assertIsNone(self.org.ocr_trial_started_at)
        self.assertEqual(OCRRead.objects.count(), 0)

    @patch('apps.ingredients.invoice_views.extract_invoice_data', return_value=INVOICE)
    def test_pdf_charges_pages_and_confirmation_survives_expiry(self, api):
        response = self.client.post(reverse('ingredients:invoice-upload'), {'invoice_file': pdf(3), 'request_id': str(uuid.uuid4())})
        self.assertRedirects(response, reverse('ingredients:invoice-confirm'))
        self.org.refresh_from_db()
        self.assertEqual(self.org.ocr_trial_pages_used, 3)
        self.org.ocr_trial_started_at = timezone.now() - timedelta(days=31)
        self.org.save()
        self.assertEqual(self.client.get(reverse('ingredients:invoice-confirm')).status_code, 200)
        self.assertEqual(self.client.get(reverse('ingredients:ingredient-list')).status_code, 200)

    @patch('apps.ingredients.invoice_views.extract_invoice_data_from_image', return_value=INVOICE)
    def test_photo_and_second_user_share_limit(self, api):
        response = self.client.post(reverse('ingredients:invoice-upload'), {'invoice_file': photo(), 'request_id': str(uuid.uuid4())})
        self.assertEqual(response.status_code, 302)
        teammate = User.objects.create_user(username='second', organization=self.org)
        self.client.force_login(teammate)
        response = self.client.get(reverse('ingredients:invoice-upload'))
        self.assertContains(response, '29 stron')

    @patch('apps.ingredients.invoice_views.extract_invoice_data_from_image', side_effect=RuntimeError('API failure'))
    def test_api_error_refunds_reservation(self, api):
        response = self.client.post(reverse('ingredients:invoice-upload'), {'invoice_file': photo(), 'request_id': str(uuid.uuid4())})
        self.assertContains(response, 'Nie odjęliśmy stron')
        self.org.refresh_from_db()
        self.assertEqual(self.org.ocr_trial_pages_used, 0)
        self.assertIsNone(self.org.ocr_trial_started_at)
        self.assertEqual(OCRRead.objects.get().status, 'failed')

    @patch('apps.ingredients.invoice_views.extract_invoice_data_from_image', return_value={'items': []})
    def test_empty_read_does_not_consume_trial(self, api):
        response = self.client.post(reverse('ingredients:invoice-upload'), {'invoice_file': photo(), 'request_id': str(uuid.uuid4())})
        self.assertContains(response, 'Nie znaleziono pozycji')
        self.org.refresh_from_db()
        self.assertIsNone(self.org.ocr_trial_started_at)
        self.assertEqual(OCRRead.objects.get().status, 'failed')

    @patch('apps.ingredients.invoice_views.extract_invoice_data_from_image')
    def test_exhausted_limit_blocks_api_and_interest_is_idempotent(self, api):
        self.org.ocr_trial_pages_used = 30
        self.org.save()
        response = self.client.post(reverse('ingredients:invoice-upload'), {'invoice_file': photo(), 'request_id': str(uuid.uuid4())})
        self.assertEqual(response.status_code, 200)
        api.assert_not_called()
        self.assertEqual(self.client.get(reverse('ingredients:invoice-request-access')).status_code, 405)
        self.client.post(reverse('ingredients:invoice-request-access'))
        self.org.refresh_from_db()
        requested = self.org.ocr_access_requested_at
        self.assertIsNotNone(requested)
        self.client.post(reverse('ingredients:invoice-request-access'))
        self.org.refresh_from_db()
        self.assertEqual(self.org.ocr_access_requested_at, requested)

    def test_corrupt_or_long_file_does_not_start_trial(self):
        for upload in [SimpleUploadedFile('bad.pdf', b'broken'), pdf(11)]:
            response = self.client.post(reverse('ingredients:invoice-estimate'), {'invoice_file': upload})
            self.assertEqual(response.status_code, 400)
        self.assertEqual(OCRRead.objects.count(), 0)

    def test_registration_setup_and_free_ocr_entry(self):
        self.client.logout()
        response = self.client.post(reverse('accounts:register'), {
            'email': 'new@example.test', 'password1': 'Local-Test-Password-123',
            'password2': 'Local-Test-Password-123', 'accept_tos': 'on',
        })
        self.assertRedirects(response, reverse('accounts:setup'))
        self.assertRedirects(self.client.post(reverse('accounts:setup'), {'name': 'Nowa restauracja'}), reverse('core:dashboard'))
        self.assertContains(self.client.get(reverse('ingredients:invoice-upload')), 'Do 30 stron gratis')
        org = User.objects.get(email='new@example.test').organization
        self.assertEqual(org.plan, Organization.PLAN_FREE)
        self.assertIsNone(org.ocr_trial_started_at)


@skipUnless(connection.vendor == 'postgresql', 'Row-lock test requires PostgreSQL')
class ConcurrentTrialTests(TransactionTestCase):
    def test_parallel_uploads_cannot_spend_same_last_pages(self):
        org = organization()
        org.ocr_trial_pages_used = 20
        org.save()
        barrier = Barrier(2)
        def attempt(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                reserve_read(org.pk, 10, uuid.uuid4())
                return True
            except ValueError:
                return False
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(attempt, range(2))), [False, True])
