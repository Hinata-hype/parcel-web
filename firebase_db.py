import os, json
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from google.cloud.firestore_v1.base_query import FieldFilter

from config import FIREBASE_KEY_PATH

_db = None  # ตัวแปรเก็บ connection ไว้ใช้ซ้ำ (ไม่ต้อง init ใหม่ทุกครั้ง)


def init_db():
    """เชื่อมต่อ Firebase ครั้งแรก (ต้องเรียกก่อนใช้ฟังก์ชันอื่นเสมอ)"""
    global _db
    if _db is not None:
        return
    if not firebase_admin._apps:  # กันการ init ซ้ำ
        key_json = os.environ.get("FIREBASE_KEY_JSON")
        cred = credentials.Certificate(json.loads(key_json) if key_json else FIREBASE_KEY_PATH)
        firebase_admin.initialize_app(cred)
    _db = firestore.client()
    print("[Firebase] เชื่อมต่อ Firestore สำเร็จ")


def add_member(name: str, telegram_chat_id: str):
    """เพิ่มสมาชิกในบ้าน"""
    doc_ref = _db.collection("members").document()
    doc_ref.set({
        "name": name,
        "telegram_chat_id": telegram_chat_id,
        "pending_tracking": []  # ลิสต์เลขพัสดุที่กำลังรออยู่ตอนนี้ (ว่างตอนสมัครใหม่)
    })
    print(f"[Firebase] เพิ่มสมาชิก '{name}' เรียบร้อยแล้ว")


def find_member_by_chat_id(telegram_chat_id: str):
    """ค้นหาว่า chat_id นี้เคยลงทะเบียนไว้แล้วหรือยัง (คืนค่า document หรือ None)"""
    docs = (
        _db.collection("members")
        .where(filter=FieldFilter("telegram_chat_id", "==", str(telegram_chat_id)))
        .limit(1)
        .stream()
    )
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        return data
    return None


def upsert_member(name: str, telegram_chat_id: str):
    """
    เพิ่มสมาชิกใหม่ หรืออัปเดตชื่อถ้า chat_id นี้เคยลงทะเบียนไว้แล้ว
    ใช้สำหรับระบบลงทะเบียนอัตโนมัติผ่านบอท (bot_listener.py)
    คืนค่า: (สำเร็จหรือไม่, เป็นสมาชิกใหม่หรืออัปเดตของเดิม)
    """
    existing = find_member_by_chat_id(telegram_chat_id)
    if existing:
        _db.collection("members").document(existing["id"]).update({"name": name})
        print(f"[Firebase] อัปเดตชื่อสมาชิก chat_id {telegram_chat_id} เป็น '{name}'")
        return True, False  # อัปเดตของเดิม ไม่ใช่สมาชิกใหม่
    else:
        add_member(name, str(telegram_chat_id))
        return True, True  # เป็นสมาชิกใหม่


def get_all_members():
    """ดึงรายชื่อสมาชิกทั้งหมด คืนค่าเป็น list ของ dict (มี key 'id' ต่อท้ายด้วย)"""
    docs = _db.collection("members").stream()
    members = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        members.append(data)
    return members


# ---------------------------------------------------------------------------
# ระบบ "จองเลข tracking ล่วงหน้า" — เพราะเลข tracking เปลี่ยนใหม่ทุกครั้งที่สั่งของ
# จะผูกเลขตายตัวกับสมาชิกไม่ได้ ต้องเก็บเป็นลิสต์ที่เพิ่ม/ลบได้ตลอด
# ---------------------------------------------------------------------------
def add_pending_tracking(member_id: str, tracking_no: str):
    """เพิ่มเลข tracking ที่กำลังรออยู่ ให้สมาชิกคนนั้น (ArrayUnion กันเพิ่มซ้ำเลขเดิม)"""
    _db.collection("members").document(member_id).update({
        "pending_tracking": firestore.ArrayUnion([tracking_no])
    })
    print(f"[Firebase] จองเลข '{tracking_no}' ให้สมาชิก {member_id} แล้ว")


def remove_pending_tracking(member_id: str, tracking_no: str):
    """ลบเลข tracking ออกจากลิสต์ที่รออยู่ หลังจากพัสดุมาถึงและแจ้งเตือนไปแล้ว"""
    _db.collection("members").document(member_id).update({
        "pending_tracking": firestore.ArrayRemove([tracking_no])
    })
    print(f"[Firebase] ลบเลข '{tracking_no}' ออกจากรายการรอของ {member_id} แล้ว")


def find_member_by_tracking(tracking_no: str):
    """
    ค้นหาว่าเลข tracking นี้มีใครจองไว้บ้าง (คืนค่า document หรือ None)
    ใช้ query สดจาก Firestore ทุกครั้ง เพราะลิสต์นี้เปลี่ยนได้ตลอดเวลาจากฝั่งบอท
    """
    docs = (
        _db.collection("members")
        .where(filter=FieldFilter("pending_tracking", "array_contains", tracking_no))
        .limit(1)
        .stream()
    )
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        return data
    return None


def log_parcel_scan(member_id, member_name, scanned_text, notified=False,
                    scanned_at=None, image_path=None):
    """บันทึกประวัติการสแกนพัสดุ"""
    doc_ref = _db.collection("parcel_logs").document()
    doc_ref.set({
        "member_id": member_id,
        "member_name": member_name,
        "scanned_text": scanned_text,
        "scanned_at": scanned_at or datetime.now().isoformat(timespec="seconds"),
        "notified": notified,
        "image_path": image_path
    })


def get_recent_logs(limit=20):
    """ดึงประวัติการสแกนล่าสุด (เผื่อนำไปทำหน้าเว็บดูย้อนหลัง)"""
    docs = (
        _db.collection("parcel_logs")
        .order_by("scanned_at", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [doc.to_dict() for doc in docs]
