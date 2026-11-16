
import os
import hmac
import secrets
import re
from io import BytesIO
from datetime import timedelta
from functools import wraps

from flask import (
    Flask, request, redirect, url_for,
    session, render_template_string, render_template, send_file, abort
)
from firebase_db import init_db, get_all_members, get_recent_logs
from scan_service import decode_frame, make_evidence, now_bangkok
import receipt_store
from web_notify import notify_receipt

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("RENDER", "").lower() == "true",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    MAX_CONTENT_LENGTH=6 * 1024 * 1024,
)

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")


def setup_ready():
    return bool(ADMIN_PASSWORD and app.secret_key and app.secret_key != "change-this-before-deploy")

PAGE = """
<!doctype html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Smart Parcel Scanner</title>
  <style>
    body { font-family: sans-serif; max-width: 1000px;
           margin: 35px auto; padding: 0 16px; color: #243047; }
    .card { background: #f4f7fb; border-radius: 12px;
            padding: 18px; margin: 14px 0; }
    table { border-collapse: collapse; width: 100%; }
    th, td { text-align: left; padding: 10px;
             border-bottom: 1px solid #ddd; }
    input, button { padding: 10px; margin: 5px 0; }
    a { color: #2458a6; }
  </style>
</head>
<body>
  <h1>Smart Parcel Scanner</h1>
  <p><a href="{{ url_for('home') }}">← หน้าแรกสำหรับผู้รับพัสดุ</a></p>
  {% if login %}
    <div class="card">
      <h2>เข้าสู่ระบบผู้ดูแล</h2>
      <form method="post">
        <input type="password" name="password" autocomplete="current-password"
               placeholder="รหัสผ่านผู้ดูแล" required>
        <button type="submit">เข้าสู่ระบบ</button>
      </form>
      {% if error %}<p>รหัสผ่านไม่ถูกต้อง</p>{% endif %}
    </div>
  {% else %}
    <p>แดชบอร์ดข้อมูลพัสดุ</p>
    <p><a href="{{ url_for('scanner') }}">📷 เปิดกล้องสแกนและบันทึกหลักฐาน</a></p>
    <p><a href="{{ url_for('bot_help') }}">วิธีเพิ่มเลขพัสดุผ่าน Telegram</a></p>
    <p><a href="{{ url_for('logout') }}">ออกจากระบบ</a></p>
    <div class="card">
      <h2>สมาชิกทั้งหมด: {{ members|length }} คน</h2>
      <table>
        <tr><th>ชื่อ</th><th>พัสดุที่รอ</th></tr>
        {% for m in members %}
        <tr>
          <td>{{ m.get('name', '-') }}</td>
          <td>{{ m.get('pending_tracking', [])|join(', ') or '-' }}</td>
        </tr>
        {% endfor %}
      </table>
    </div>
    <div class="card">
      <h2>ประวัติสแกนล่าสุด</h2>
      <table>
        <tr><th>ชื่อ</th><th>ข้อความที่สแกน</th>
            <th>เวลา</th><th>แจ้งเตือน</th><th>หลักฐานรับเข้าจุดรับ</th></tr>
        {% for log in logs %}
        <tr>
          <td>{{ log.get('member_name', '-') }}</td>
          <td>{{ log.get('scanned_text', '-') }}</td>
          <td>{{ log.get('scanned_at', '-') }}</td>
          <td>{{ 'สำเร็จ' if log.get('notified') else 'ไม่สำเร็จ' }}</td>
          <td>{% if log.get('evidence_id') %}<a href="{{ url_for('receipt_detail', identifier=log.evidence_id) }}">ดูภาพและสถานะ</a>{% else %}รายการเดิม ไม่มีภาพบนเว็บ{% endif %}</td>
        </tr>
        {% endfor %}
      </table>
    </div>
  {% endif %}
</body>
</html>
"""


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not setup_ready():
            if request.path.startswith('/api/'):
                return {"error": "ตั้ง SECRET_KEY และ ADMIN_PASSWORD ก่อนใช้งาน"}, 503
            return "Server setup required: configure SECRET_KEY and ADMIN_PASSWORD.", 503
        if not session.get("admin"):
            if request.path.startswith('/api/'):
                return {"error": "กรุณาเข้าสู่ระบบใหม่"}, 401
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def csrf_valid():
    supplied = request.headers.get("X-CSRF-Token", "")
    return bool(session.get("csrf") and hmac.compare_digest(supplied, session["csrf"]))


@app.after_request
def private_response(response):
    if request.path != '/health' and not request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    return response


@app.errorhandler(413)
def upload_too_large(error):
    return {"error": "ภาพมีขนาดใหญ่เกินไป กรุณาใช้ไฟล์ไม่เกิน 5 MB"}, 413


def valid_receipt_id(identifier):
    if not re.fullmatch(r"web_[0-9a-f]{64}", identifier):
        abort(404)


def public_receipt(record, duplicate=False):
    return {
        "status": "duplicate" if duplicate else "received",
        "member_name": record["member_name"], "tracking_no": record["tracking_no"],
        "scanned_at": record["scanned_at"], "notified": bool(record.get("notified")),
        "evidence_url": url_for('evidence', identifier=record["evidence_id"]),
        "receipt_url": url_for('receipt_detail', identifier=record["evidence_id"]),
    }


@app.get('/scan')
@admin_required
def scanner():
    return render_template('scanner.html', csrf=csrf_token())


@app.get('/bot-help')
def bot_help():
    return render_template('bot_help.html')


@app.post('/api/scan')
@admin_required
def scan_frame():
    if not csrf_valid():
        return {"error": "เซสชันไม่ถูกต้อง กรุณารีเฟรชหน้าเว็บ"}, 403
    upload = request.files.get('image')
    if upload is None:
        return {"error": "กรุณาส่งภาพจากกล้องหรือเลือกไฟล์ภาพ"}, 400
    try:
        image, codes = decode_frame(upload.read())
        if not codes:
            return {"status": "no_code", "message": "ยังอ่านเลขไม่ได้ ถือป้ายให้นิ่งและเพิ่มแสง"}
        init_db()
        candidates, previous = [], []
        for code in codes[:10]:
            old = receipt_store.get_receipt(code)
            if old:
                previous.append(old)
                continue
            owners = receipt_store.pending_members(code)
            if len(owners) > 1:
                return {"status": "conflict", "message": "เลขเดียวกันถูกจองหลายคน กรุณาตรวจสอบเจ้าของก่อนรับพัสดุ"}
            if owners:
                candidates.append((code, owners[0]))
        if len(candidates) > 1:
            return {"status": "multiple", "message": "พบหลายเลขที่รอรับ กรุณาแสดงป้ายพัสดุทีละชิ้น"}
        if not candidates:
            if previous:
                return public_receipt(previous[0], duplicate=True)
            return {"status": "unknown", "message": "ไม่พบเลขที่จองไว้ ให้ผู้รับส่ง /addparcel ในบอทก่อน", "codes": codes[:10]}
        tracking, member = candidates[0]
        when = now_bangkok()
        jpeg = make_evidence(image, tracking, when)
        record, created = receipt_store.save_receipt(member, tracking, jpeg, when)
        if created:
            try:
                record['notified'] = notify_receipt(record['id'])
            except Exception:
                # Receipt is already committed. Never tell the operator to receive again.
                record['notified'] = False
        return public_receipt(record, duplicate=not created)
    except ValueError as exc:
        return {"error": str(exc)}, 400
    except Exception:
        app.logger.error('Scan failed; receipt may need to be checked by rescanning.')
        return {"error": "ยังยืนยันการบันทึกไม่ได้ กรุณาสแกนซ้ำเพื่อตรวจสอบ ระบบจะไม่สร้างรายการรับซ้ำ"}, 503


@app.get('/evidence/<identifier>')
@admin_required
def evidence(identifier):
    valid_receipt_id(identifier)
    init_db()
    jpeg = receipt_store.evidence_bytes(identifier)
    if not jpeg:
        abort(404)
    return send_file(BytesIO(jpeg), mimetype='image/jpeg', download_name=f'{identifier}.jpg')


@app.get('/receipts/<identifier>')
@admin_required
def receipt_detail(identifier):
    valid_receipt_id(identifier)
    init_db()
    import firebase_db
    doc = firebase_db._db.collection('parcel_logs').document(identifier).get()
    if not doc.exists:
        abort(404)
    return render_template('receipt.html', receipt=doc.to_dict(), identifier=identifier, csrf=csrf_token())


@app.post('/api/receipts/<identifier>/notify')
@admin_required
def retry_notification(identifier):
    valid_receipt_id(identifier)
    if not csrf_valid():
        return {"error": "กรุณารีเฟรชหน้าเว็บก่อนลองใหม่"}, 403
    try:
        init_db()
        success = notify_receipt(identifier)
        return {"notified": success, "message": "ส่ง Telegram สำเร็จ" if success else
                "ยังส่งไม่สำเร็จ หรือมีคำขอส่งอยู่ กรุณาตรวจ token และให้ผู้รับกด Start ในบอทก่อน"}
    except Exception:
        return {"error": "ยังยืนยันการส่งไม่ได้ ภาพหลักฐานยังถูกเก็บไว้แล้ว"}, 503


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/login", methods=["GET", "POST"])
def login():
    if not setup_ready():
        return "Server setup required: configure SECRET_KEY and ADMIN_PASSWORD.", 503
    error = False
    if request.method == "POST":
        if hmac.compare_digest(request.form.get("password", "").encode(), ADMIN_PASSWORD.encode()):
            session.clear()
            session["admin"] = True
            session.permanent = True
            return redirect(url_for("dashboard"))
        error = True
    return render_template_string(PAGE, login=True, error=error)


@app.get("/")
def home():
    return render_template("home.html")


@app.route("/admin")
@admin_required
def dashboard():
    try:
        init_db()
        members = get_all_members()
        logs = get_recent_logs(30)
        return render_template_string(
            PAGE, login=False, members=members, logs=logs
        )
    except Exception:
        app.logger.error("Dashboard failed; check Firebase configuration and connectivity.")
        return "ไม่สามารถโหลดข้อมูลได้ กรุณาตรวจสอบการตั้งค่า Firebase", 500


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))
