from io import BytesIO
import unittest
from unittest.mock import patch
from PIL import Image
import zxingcpp

import web_app
from scan_service import decode_frame, make_evidence, MAX_EVIDENCE
from receipt_store import receipt_id


TRACKING = 'JTTH203447892502'
IDENTIFIER = receipt_id(TRACKING)
MEMBER = {'id': 'test-member', 'name': 'Test Recipient', 'telegram_chat_id': '123'}


def barcode_png(text=TRACKING, format=zxingcpp.BarcodeFormat.Code128):
    barcode = zxingcpp.create_barcode(text, format)
    image = Image.fromarray(zxingcpp.write_barcode_to_image(barcode, scale=3))
    out = BytesIO()
    image.save(out, format='PNG')
    return out.getvalue()


def record():
    return {'id': IDENTIFIER, 'evidence_id': IDENTIFIER, 'member_name': 'Test Recipient',
            'tracking_no': TRACKING, 'scanned_at': '2026-10-29T14:00:00+07:00', 'notified': False}


class ImageTests(unittest.TestCase):
    def test_real_code128_and_qr_decode(self):
        for format in [zxingcpp.BarcodeFormat.Code128, zxingcpp.BarcodeFormat.QRCode]:
            with self.subTest(format=format):
                image, codes = decode_frame(barcode_png(format=format))
                self.assertEqual(codes, [TRACKING])
                jpeg = make_evidence(image, TRACKING, record()['scanned_at'])
                self.assertLessEqual(len(jpeg), MAX_EVIDENCE)
                proof = Image.open(BytesIO(jpeg))
                self.assertEqual(proof.format, 'JPEG')
                self.assertGreater(proof.height, image.height)

    def test_reject_invalid_or_large_images(self):
        for raw in [b'not an image', b'a' * (5 * 1024 * 1024 + 1)]:
            with self.assertRaises(ValueError):
                decode_frame(raw)


class ScanAPITests(unittest.TestCase):
    def setUp(self):
        patches = [patch.dict(web_app.app.config, SECRET_KEY='test-secret', TESTING=True),
                   patch.object(web_app, 'ADMIN_PASSWORD', 'test-password'),
                   patch.object(web_app, 'init_db')]
        for p in patches:
            p.start(); self.addCleanup(p.stop)
        self.client = web_app.app.test_client()
        with self.client.session_transaction() as session:
            session['admin'] = True
            session['csrf'] = 'test-csrf'

    def scan(self, raw=None, csrf=True):
        return self.client.post('/api/scan', data={'image': (BytesIO(raw or barcode_png()), 'frame.png')},
                                headers={'X-CSRF-Token':'test-csrf'} if csrf else {})

    def test_scan_page_has_camera_and_csrf(self):
        response = self.client.get('/scan')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<video', response.data)
        self.assertIn(b'test-csrf', response.data)

    def test_public_scan_requires_csrf_and_evidence_stays_private(self):
        self.assertEqual(self.scan(csrf=False).status_code, 403)
        with self.client.session_transaction() as session:
            session.clear()
        self.assertEqual(self.scan().status_code, 403)
        self.assertEqual(self.client.get('/evidence/' + IDENTIFIER).status_code, 302)

    def test_public_scan_saves_but_never_exposes_recipient_or_old_evidence(self):
        with self.client.session_transaction() as session:
            session.pop('admin')
        for duplicate in (False, True):
            with self.subTest(duplicate=duplicate), \
                 patch.object(web_app.receipt_store, 'get_receipt', return_value=record() if duplicate else None), \
                 patch.object(web_app.receipt_store, 'pending_members', return_value=[MEMBER]), \
                 patch.object(web_app.receipt_store, 'save_receipt', return_value=(record(), True)) as save, \
                 patch.object(web_app, 'notify_receipt', return_value=True) as notify:
                response = self.scan()
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json['status'], 'duplicate' if duplicate else 'received')
                self.assertEqual(set(response.json), {'status', 'tracking_no', 'notified'})
                if duplicate:
                    save.assert_not_called(); notify.assert_not_called()
                else:
                    save.assert_called_once(); notify.assert_called_once()
        endpoint = '/api/receipts/' + IDENTIFIER + '/notify'
        self.assertEqual(self.client.post(endpoint, headers={'X-CSRF-Token':'test-csrf'}).status_code, 401)

    def test_unknown_tracking_does_not_save_or_notify(self):
        with patch.object(web_app.receipt_store, 'get_receipt', return_value=None), \
             patch.object(web_app.receipt_store, 'pending_members', return_value=[]), \
             patch.object(web_app.receipt_store, 'save_receipt') as save, \
             patch.object(web_app, 'notify_receipt') as notify:
            self.assertEqual(self.scan().json['status'], 'unknown')
            save.assert_not_called(); notify.assert_not_called()

    def test_duplicate_does_not_save_or_notify_again(self):
        with patch.object(web_app.receipt_store, 'get_receipt', return_value=record()), \
             patch.object(web_app.receipt_store, 'save_receipt') as save, \
             patch.object(web_app, 'notify_receipt') as notify:
            response = self.scan()
            self.assertEqual(response.json['status'], 'duplicate')
            self.assertEqual(response.json['evidence_url'], '/evidence/' + IDENTIFIER)
            save.assert_not_called(); notify.assert_not_called()

    def test_receipt_survives_telegram_failure(self):
        with patch.object(web_app.receipt_store, 'get_receipt', return_value=None), \
             patch.object(web_app.receipt_store, 'pending_members', return_value=[MEMBER]), \
             patch.object(web_app.receipt_store, 'save_receipt', return_value=(record(), True)) as save, \
             patch.object(web_app, 'notify_receipt', side_effect=RuntimeError('network')):
            response = self.scan()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['status'], 'received')
            self.assertFalse(response.json['notified'])
            self.assertEqual(Image.open(BytesIO(save.call_args.args[2])).format, 'JPEG')

    def test_successful_notification_and_no_recipient_id_exposure(self):
        with patch.object(web_app.receipt_store, 'get_receipt', return_value=None), \
             patch.object(web_app.receipt_store, 'pending_members', return_value=[MEMBER]), \
             patch.object(web_app.receipt_store, 'save_receipt', return_value=(record(), True)), \
             patch.object(web_app, 'notify_receipt', return_value=True):
            response = self.scan()
            self.assertTrue(response.json['notified'])
            self.assertNotIn('telegram_chat_id', response.json)

    def test_multiple_owners_are_not_auto_selected(self):
        with patch.object(web_app.receipt_store, 'get_receipt', return_value=None), \
             patch.object(web_app.receipt_store, 'pending_members', return_value=[MEMBER, MEMBER]), \
             patch.object(web_app.receipt_store, 'save_receipt') as save:
            self.assertEqual(self.scan().json['status'], 'conflict')
            save.assert_not_called()

    def test_database_failure_never_reports_received(self):
        with patch.object(web_app.receipt_store, 'get_receipt', side_effect=RuntimeError('credentials')):
            response = self.scan()
            self.assertEqual(response.status_code, 503)
            self.assertNotIn(b'credentials', response.data)

    def test_invalid_image_and_no_barcode(self):
        self.assertEqual(self.scan(b'bad image').status_code, 400)
        output = BytesIO(); Image.new('RGB', (100,100), 'white').save(output, format='PNG')
        self.assertEqual(self.scan(output.getvalue()).json['status'], 'no_code')

    def test_private_evidence_returns_jpeg_and_no_cache(self):
        with patch.object(web_app.receipt_store, 'evidence_bytes', return_value=b'jpeg-data'):
            response = self.client.get('/evidence/' + IDENTIFIER)
            self.assertEqual(response.mimetype, 'image/jpeg')
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(self.client.get('/evidence/not-a-receipt').status_code, 404)

    def test_retry_requires_csrf_and_reports_result(self):
        endpoint = '/api/receipts/' + IDENTIFIER + '/notify'
        self.assertEqual(self.client.post(endpoint).status_code, 403)
        with patch.object(web_app, 'notify_receipt', return_value=True):
            self.assertTrue(self.client.post(endpoint, headers={'X-CSRF-Token':'test-csrf'}).json['notified'])


if __name__ == '__main__':
    unittest.main()
