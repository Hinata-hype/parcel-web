"""Atomic receipt + evidence + booking removal, separate from Telegram status."""
import hashlib
from datetime import datetime, timedelta, timezone
import uuid

from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
import firebase_db


def receipt_id(tracking):
    return "web_" + hashlib.sha256(tracking.encode()).hexdigest()


def get_receipt(tracking):
    doc = firebase_db._db.collection("parcel_logs").document(receipt_id(tracking)).get()
    return dict(doc.to_dict(), id=doc.id) if doc.exists else None


def pending_members(tracking):
    docs = (firebase_db._db.collection("members")
            .where(filter=FieldFilter("pending_tracking", "array_contains", tracking))
            .limit(2).stream())
    return [dict(doc.to_dict(), id=doc.id) for doc in docs]


def save_receipt(member, tracking, jpeg, scanned_at):
    db = firebase_db._db
    log_ref = db.collection("parcel_logs").document(receipt_id(tracking))
    evidence_ref = db.collection("parcel_evidence").document(log_ref.id)
    member_ref = db.collection("members").document(member["id"])

    @firestore.transactional
    def commit(transaction):
        previous = log_ref.get(transaction=transaction)
        if previous.exists:
            return dict(previous.to_dict(), id=previous.id), False
        current = member_ref.get(transaction=transaction)
        data = current.to_dict() if current.exists else {}
        if tracking not in data.get("pending_tracking", []):
            raise ValueError("เลขพัสดุนี้ไม่ได้อยู่ในรายการรอแล้ว กรุณาสแกนใหม่")
        record = {
            "member_id": member["id"], "member_name": data["name"],
            "telegram_chat_id": data.get("telegram_chat_id", ""),
            "tracking_no": tracking, "scanned_text": f"tracking_no={tracking}",
            "scanned_at": scanned_at, "receipt_status": "received",
            "source": "web", "evidence_id": log_ref.id,
            "evidence_sha256": hashlib.sha256(jpeg).hexdigest(),
            "notified": False, "notification_status": "pending",
        }
        transaction.set(evidence_ref, {"jpeg": jpeg, "scanned_at": scanned_at})
        transaction.set(log_ref, record)
        transaction.update(member_ref, {"pending_tracking": firestore.ArrayRemove([tracking])})
        return dict(record, id=log_ref.id), True

    return commit(db.transaction())


def evidence_bytes(identifier):
    doc = firebase_db._db.collection("parcel_evidence").document(identifier).get()
    return doc.to_dict().get("jpeg") if doc.exists else None


def claim_notification(identifier):
    ref = firebase_db._db.collection("parcel_logs").document(identifier)
    now = datetime.now(timezone.utc)
    claim = uuid.uuid4().hex

    @firestore.transactional
    def claim_tx(transaction):
        doc = ref.get(transaction=transaction)
        if not doc.exists or doc.to_dict().get("source") != "web":
            raise ValueError("ไม่พบรายการรับพัสดุ")
        data = doc.to_dict()
        if data.get("notified"):
            return data, None
        if data.get("notification_lease_until", now) > now:
            return data, None
        transaction.update(ref, {
            "notification_claim": claim, "notification_status": "sending",
            "notification_lease_until": now + timedelta(minutes=2),
        })
        return data, claim

    return claim_tx(firebase_db._db.transaction())


def finish_notification(identifier, claim, success):
    ref = firebase_db._db.collection("parcel_logs").document(identifier)

    @firestore.transactional
    def finish_tx(transaction):
        doc = ref.get(transaction=transaction)
        if doc.to_dict().get("notification_claim") == claim:
            transaction.update(ref, {
                "notified": success,
                "notification_status": "sent" if success else "failed",
                "notification_lease_until": firestore.DELETE_FIELD,
                "notification_claim": firestore.DELETE_FIELD,
            })

    finish_tx(firebase_db._db.transaction())
