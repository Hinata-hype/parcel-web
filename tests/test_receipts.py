import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import receipt_store as store


def snapshot(data=None, identifier='id'):
    result = MagicMock()
    result.exists = data is not None
    result.id = identifier
    result.to_dict.return_value = data
    return result


class ReceiptTransactionTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.tx = self.db.transaction.return_value
        self.log = MagicMock(id=store.receipt_id('TEST1234'))
        self.member = MagicMock()
        self.evidence = MagicMock()
        refs = {'parcel_logs':self.log, 'members':self.member, 'parcel_evidence':self.evidence}
        self.db.collection.side_effect = lambda name: MagicMock(document=MagicMock(return_value=refs[name]))
        for p in [patch.object(store.firebase_db, '_db', self.db),
                  patch.object(store.firestore, 'transactional', side_effect=lambda fn: fn)]:
            p.start(); self.addCleanup(p.stop)

    def test_evidence_log_and_booking_update_share_one_transaction(self):
        self.log.get.return_value = snapshot()
        self.member.get.return_value = snapshot({'name':'Test', 'pending_tracking':['TEST1234'], 'telegram_chat_id':'123'})
        record, created = store.save_receipt({'id':'member'}, 'TEST1234', b'jpeg', 'timestamp')
        self.assertTrue(created)
        self.assertFalse(record['notified'])
        self.assertEqual(record['receipt_status'], 'received')
        self.assertEqual(self.tx.set.call_count, 2)
        self.assertEqual(self.tx.set.call_args_list[0].args[0], self.evidence)
        self.assertEqual(self.tx.set.call_args_list[0].args[1]['jpeg'], b'jpeg')
        self.tx.update.assert_called_once()
        self.assertEqual(self.tx.update.call_args.args[0], self.member)
        self.log.get.assert_called_once_with(transaction=self.tx)
        self.member.get.assert_called_once_with(transaction=self.tx)

    def test_transaction_recheck_prevents_duplicate_writes(self):
        self.log.get.return_value = snapshot({'tracking_no':'TEST1234'})
        _, created = store.save_receipt({'id':'member'}, 'TEST1234', b'jpeg', 'timestamp')
        self.assertFalse(created)
        self.tx.set.assert_not_called(); self.tx.update.assert_not_called()

    def test_removed_booking_aborts_before_any_write(self):
        self.log.get.return_value = snapshot()
        self.member.get.return_value = snapshot({'pending_tracking':[]})
        with self.assertRaises(ValueError):
            store.save_receipt({'id':'member'}, 'TEST1234', b'jpeg', 'timestamp')
        self.tx.set.assert_not_called(); self.tx.update.assert_not_called()

    def test_already_sent_notification_is_not_claimed_again(self):
        self.log.get.return_value = snapshot({'source':'web', 'notified':True})
        _, claim = store.claim_notification(self.log.id)
        self.assertIsNone(claim); self.tx.update.assert_not_called()

    def test_active_notification_lease_blocks_second_sender(self):
        self.log.get.return_value = snapshot({'source':'web', 'notified':False,
            'notification_lease_until':datetime.now(timezone.utc) + timedelta(minutes=1)})
        _, claim = store.claim_notification(self.log.id)
        self.assertIsNone(claim); self.tx.update.assert_not_called()

    def test_failed_notification_does_not_remove_receipt(self):
        self.log.get.return_value = snapshot({'notification_claim':'claim'})
        store.finish_notification(self.log.id, 'claim', False)
        data = self.tx.update.call_args.args[1]
        self.assertEqual(data['notification_status'], 'failed')
        self.assertFalse(data['notified'])
        self.assertNotIn('receipt_status', data)
        self.tx.delete.assert_not_called()

    def test_old_notification_claim_cannot_overwrite_newer_result(self):
        self.log.get.return_value = snapshot({'notification_claim':'new-claim'})
        store.finish_notification(self.log.id, 'old-claim', False)
        self.tx.update.assert_not_called()
