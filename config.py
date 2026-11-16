"""
config.py
------------------------------------------------
ไฟล์เก็บค่าตั้งค่าต่าง ๆ ของระบบ
แก้ไขค่าตรงนี้ให้ตรงกับของจริงก่อนใช้งาน
------------------------------------------------
"""

# ---------- Telegram Bot ----------
# สร้างบอทผ่าน @BotFather ใน Telegram แล้วนำ Token มาใส่ตรงนี้
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=False)
# Local checkout can share the scanner's token; a standalone deployment uses env.
load_dotenv(BASE_DIR.parent / ".env", override=False)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

# ---------- ฐานข้อมูล (แบบเก่า SQLite - เก็บไว้เผื่ออยากสลับกลับมาใช้) ----------
DATABASE_PATH = "parcel_system.db"

# ---------- Firebase Firestore ----------
# path ของไฟล์ Service Account Key ที่ดาวน์โหลดจาก Firebase Console
_key = os.environ.get("FIREBASE_KEY_PATH", "firebase_key.json")
_candidate = BASE_DIR / _key
if not _candidate.exists() and (BASE_DIR.parent / _key).exists():
    _candidate = BASE_DIR.parent / _key
FIREBASE_KEY_PATH = str(_candidate.resolve())

# ---------- YOLO (ตรวจจับกล่องพัสดุอัตโนมัติ) ----------
# ใช้โมเดลเล็กสุด (nano) เพื่อความเร็ว เหมาะกับคอมทั่วไปที่ไม่มี GPU แรง ๆ
YOLO_MODEL_PATH = "yolov8n.pt"
# ความมั่นใจขั้นต่ำที่จะถือว่า "เจอวัตถุ" (0.0 - 1.0)
YOLO_CONFIDENCE = 0.35
# ต้องเห็นกล่องอยู่นิ่ง ๆ ในเฟรมติดต่อกันกี่เฟรม ก่อนจะสั่งสแกนอัตโนมัติ
# (กันไม่ให้สแกนรัวเกินไปตอนกล่องกำลังเคลื่อนที่ผ่านจอ)
STABLE_FRAMES_REQUIRED = 15
# หลังจากสแกนไปแล้ว ต้องรอกี่วินาทีก่อนจะสแกนกล่องถัดไปได้
SCAN_COOLDOWN_SECONDS = 5

# ---------- กล้อง ----------
CAMERA_INDEX = 1          # 0 คือกล้องเว็บแคมตัวแรกของเครื่อง
OCR_LANGUAGE = "tha+eng"  # ใช้ Tesseract อ่านได้ทั้งไทยและอังกฤษ
# ---------- Tesseract OCR path (สำหรับ Windows เท่านั้น) ----------
TESSERACT_PATH_WINDOWS = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ---------- เสียงติ๊ด ----------
BEEP_SOUND_PATH = "beep.wav"

# ---------- ความแม่นยำในการจับคู่ชื่อ ----------
# ค่ายิ่งสูง ยิ่งต้องการให้ข้อความตรงกันมาก (0-100)
NAME_MATCH_THRESHOLD = 70
