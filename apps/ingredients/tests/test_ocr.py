import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import fitz
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from apps.accounts.models import Organization, User
from apps.ingredients.models import Ingredient, Supplier, SupplierPrice
from apps.ingredients.ocr_service import (
    normalize_items, _call_openai_vision, extract_invoice_data,
    extract_invoice_data_from_image, pdf_to_images_base64,
)


def item(**kwargs):
    return dict(name='Mąka typ 500 5kg', price=20, quantity=5,
                purchased_quantity=3, unit='kg', price_type='za_opakowanie',
                is_netto=True, vat=5, **kwargs)


class InvoiceExtractionTests(SimpleTestCase):
    def test_package_price_is_not_divided_by_purchase_count(self):
        normalized = normalize_items([item()])[0]
        self.assertEqual(normalized['price'], Decimal('20'))
        self.assertEqual(normalized['price_per_unit'], Decimal('4'))
        self.assertEqual(normalized['package_size'], Decimal('5'))
        self.assertEqual(normalized['purchased_quantity'], 3)

    def test_unreadable_price_does_not_become_zero(self):
        data = item()
        for bad in [None, 'NaN', 'Infinity', -1]:
            data['price'] = bad
            with self.subTest(price=bad), self.assertRaises(ValueError):
                normalize_items([data])

    def test_unit_price_and_gross_are_preserved(self):
        data = item()
        data.update(price_type='za_jednostke', quantity=None, price=3, is_netto=False)
        result = normalize_items([data])[0]
        self.assertEqual(result['price_per_unit'], Decimal('3'))
        self.assertIsNone(result['package_size'])
        self.assertFalse(result['is_netto'])

    def test_unknown_package_size_is_not_guessed(self):
        data = item()
        for bad in [None, 0, -5, 'NaN']:
            data['quantity'] = bad
            with self.subTest(quantity=bad), self.assertRaises(ValueError):
                normalize_items([data])

    @override_settings(OPENAI_API_KEY='test', OPENAI_OCR_MODEL='gpt-4.1-mini')
    @patch('openai.OpenAI')
    def test_schema_and_incomplete_response(self, client):
        create = client.return_value.__enter__.return_value.chat.completions.create
        choice = SimpleNamespace(finish_reason='stop', message=SimpleNamespace(refusal=None, content=json.dumps({'items': []})))
        create.return_value = SimpleNamespace(choices=[choice])
        self.assertEqual(_call_openai_vision([]), {'items': []})
        self.assertEqual(create.call_args.kwargs['model'], 'gpt-4.1-mini')
        self.assertTrue(create.call_args.kwargs['response_format']['json_schema']['strict'])
        for reason in ['length', 'content_filter']:
            choice.finish_reason = reason
            with self.assertRaises(ValueError):
                _call_openai_vision([])

    @patch('apps.ingredients.ocr_service._call_openai_vision', return_value={'items': []})
    def test_pdf_and_photo_use_same_extraction(self, call):
        with fitz.open() as doc:
            doc.new_page().insert_text((72, 72), 'Invoice test')
            pdf = doc.tobytes()
        extract_invoice_data(pdf)
        self.assertTrue(call.call_args.args[0][1]['image_url']['url'].startswith('data:image/png;base64,'))
        extract_invoice_data_from_image(b'photo', 'image/jpeg')
        self.assertTrue(call.call_args.args[0][1]['image_url']['url'].startswith('data:image/jpeg;base64,'))

    def test_long_pdf_is_not_silently_truncated(self):
        with fitz.open() as doc:
            for _ in range(11):
                doc.new_page()
            with self.assertRaises(ValueError):
                pdf_to_images_base64(doc.tobytes())


class InvoiceConfirmationTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='OCR test', slug='ocr-test', plan='pro', accepted_tos_at=timezone.now())
        self.user = User.objects.create_user(username='ocr-test', email='ocr@example.test', password='test-password', organization=self.org, role=User.ROLE_OWNER)
        self.supplier = Supplier.objects.create(organization=self.org, name='Test Supplier')
        self.ingredient = Ingredient.objects.create(organization=self.org, name='Mąka', base_unit='kg')
        self.client.force_login(self.user)
        session = self.client.session
        session['invoice_items'] = [{'name': 'Mąka', 'price': '20', 'price_per_unit': '4', 'unit': 'kg', 'package_size': '5', 'is_netto': True, 'purchased_quantity': 3, 'matched_ingredient_id': self.ingredient.pk}]
        session['invoice_meta'] = {}
        session.save()

    def test_single_form_fields_on_both_screen_sizes(self):
        response = self.client.get(reverse('ingredients:invoice-confirm'))
        self.assertEqual(response.status_code, 200)
        for field in ['price_0', 'unit_0', 'package_size_0', 'is_netto_0', 'ingredient_id_0', 'save_0']:
            self.assertContains(response, f'name="{field}"', count=1)
        self.assertContains(response, 'value="20"')

    def test_package_price_is_divided_once_at_save(self):
        response = self.client.post(reverse('ingredients:invoice-confirm'), {
            'supplier_choice': self.supplier.pk, 'save_0': 'on',
            'ingredient_id_0': self.ingredient.pk, 'price_0': '20',
            'unit_0': 'kg', 'package_size_0': '5', 'is_netto_0': '1',
        })
        self.assertEqual(response.status_code, 302)
        price = SupplierPrice.objects.get()
        self.assertEqual(price.price, Decimal('20'))
        self.assertEqual(price.price_per_base_unit, Decimal('4'))
