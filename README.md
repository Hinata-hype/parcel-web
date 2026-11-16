# Smart Parcel Scanner — เว็บสแกนและหลักฐาน

## เว็บออนไลน์และสิทธิ์ใช้งาน

หน้าแรก https://smart-parcel-scanner.onrender.com/ และ /scan เปิดให้คนส่งของสแกนรับเข้าจุดรับได้โดยไม่ต้องล็อกอิน กดเปิดกล้องและอนุญาตกล้องก่อนใช้งาน ส่วนเพิ่มเลขและตรวจเลขผ่าน @KittiSmartParcel_bot อยู่ด้านล่าง และ /bot-help เป็นคู่มือสาธารณะ

ส่วนผู้ดูแลอยู่ที่ /admin ต้องเข้าสู่ระบบก่อนดูรายชื่อ ประวัติรวม เปิดภาพหลักฐาน หรือสั่งส่งแจ้งเตือนซ้ำ ผู้ใช้ทั่วไปเข้าถึงข้อมูลเหล่านี้ไม่ได้

เปลี่ยนรหัสผู้ดูแลออนไลน์ใน Render Dashboard ของ smart-parcel-scanner → Environment → Secret Files → .env → แก้ค่า ADMIN_PASSWORD แล้วบันทึกและ deploy ใหม่ ไม่ต้องแก้ไฟล์บน GitHub

หากใช้งาน local ด้วย ให้แก้ ADMIN_PASSWORD ใน parcel-web/.env แล้วเปิด start_web.bat ใหม่ การแก้ไฟล์บนเครื่องไม่เปลี่ยนค่าบน Render โดยอัตโนมัติ

## เปิดใช้งานบน Windows

จากโฟลเดอร์หลัก ดับเบิลคลิก `start_web.bat` หากยังไม่ตั้ง ADMIN_PASSWORD โปรแกรมจะให้พิมพ์รหัสผ่านเอง (ไม่แสดงตัวอักษรขณะพิมพ์) และไม่ยอมรับรหัสว่าง รหัสที่กรอกใช้เฉพาะการเปิดเว็บรอบนั้น
เปิด http://127.0.0.1:5000/ เพื่อสแกนได้เลย รหัสใช้สำหรับ /admin เท่านั้น
หากเว็บเก่ากำลังทำงานบนพอร์ต 5000 ให้หยุดด้วย Ctrl+C ก่อนเปิดใหม่
เครื่องนี้ตั้งรหัสเว็บถาวรใน parcel-web/.env แล้ว ดูบรรทัด ADMIN_PASSWORD (ห้ามแชร์ไฟล์นี้)

ติดตั้งจากโฟลเดอร์หลัก: `.\.venv\Scripts\python.exe -m pip install -r parcel-web/requirements.txt`
หรือจาก repo เว็บ standalone: `python -m venv .venv` แล้วติดตั้ง requirements.txt

## กล้องบนเว็บ

- เปิด /scan กดเปิดกล้อง อนุญาตสิทธิ์กล้อง และเลือกกล้องที่ต้องการ
- หน้าเว็บส่งภาพไปอ่านบาร์โค้ด/QR บนเซิร์ฟเวอร์ทีละภาพ ไม่ต้องใช้ BarcodeDetector ของเบราว์เซอร์
- แสดงป้ายทีละชิ้น เลขต้องถูกจองผ่านบอทก่อน หากไม่พบเลข จะหยุดให้เพิ่มเลขแล้วเปิดกล้องใหม่
- เมื่อรับสำเร็จ กล้องหยุด แสดงเลข สถานะแจ้งเตือน และภาพที่เพิ่งส่ง กดสแกนพัสดุถัดไปเพื่อเริ่มใหม่ ผู้ดูแลที่ล็อกอินจะเห็นชื่อ เวลา และลิงก์หลักฐานเพิ่มเติม
- ถ้าเปิดกล้องไม่ได้ ใช้ “ใช้ภาพถ่ายแทนกล้อง” รองรับ JPEG/PNG/WebP ไม่เกิน 5 MB และ 16 ล้านพิกเซล
- กล้องต้องใช้ localhost หรือ HTTPS ถ้าเปิดผ่าน IP เครือข่ายแบบ HTTP อาจใช้กล้องไม่ได้
- ไม่ต้องเปิด main.py พร้อมกับเว็บ เพราะโปรแกรมอาจแย่งใช้กล้องเดียวกัน

## บอท Telegram

ตั้ง TELEGRAM_BOT_TOKEN ใน `.env` ของโปรเจกต์หลัก แล้วเปิด `start_bot.bat` ค้างไว้หนึ่งชุด
เว็บอ่าน token จาก parcel-web/.env ก่อน แล้วใช้ parent .env เป็น fallback; environment ที่ตั้งใน terminal มีลำดับสูงสุด
ให้สมาชิกค้นหา username ของบอทใน Telegram (ดูได้จาก @BotFather → /mybots):

1. ส่ง /start แล้วพิมพ์ชื่อผู้รับตามป้าย
2. ส่ง /addparcel แล้วส่งเลขพัสดุ หรือ `/addparcel JTTH203447892502`
3. รอคำตอบ “บันทึกแล้ว” และตรวจด้วย /myparcels
4. ใช้ /cancel ยกเลิกการกรอก หรือ /start เพื่อเปลี่ยนชื่อ

ทุกส่วนต้องใช้ Firebase โปรเจกต์เดียวกัน เว็บไม่รัน bot polling; บอทยังคงเป็นโปรแกรม local แยกต่างหาก
เปิด /bot-help เพื่อดูคำแนะนำในเว็บ

## หลักฐานและสถานะ

เลขที่สแกนได้มาจากภาพที่ส่งจริง ไม่รับเลขที่พิมพ์แทนภาพ
transaction ของ Firestore บันทึกภาพ JPEG ใน parcel_evidence และข้อมูลรับของใน parcel_logs พร้อมลบ pending_tracking เป็นชุดเดียว
ภาพมีเวลา Asia/Bangkok และเลขพัสดุ ไม่เกิน 450,000 bytes ต่อเอกสาร และเก็บ SHA-256 ไว้ในประวัติ
ภาพอยู่ในฐานข้อมูล จึงไม่หายตามดิสก์ชั่วคราวของ Render; ใช้พื้นที่และโควต้า Firestore ตามจำนวนภาพ

“รับเข้าจุดรับพัสดุแล้ว” แยกจาก “ส่ง Telegram สำเร็จ” หาก Telegram ล้มเหลว หลักฐานยังอยู่และกดลองส่งใหม่ได้จากหน้าหลักฐาน
การส่ง Telegram มี lease กันผู้ส่งซ้อนและจะไม่ส่งซ้ำเมื่อยืนยันสำเร็จแล้ว แต่หาก network timeout หลัง Telegram รับข้อความ อาจส่งซ้ำได้เมื่อลองใหม่
การรับเลขเดิมบนเว็บจะคืนหลักฐานเดิม ไม่สร้างรายการใหม่; เลขเดิมที่เคยรับแล้วไม่สามารถใช้จองซ้ำได้ในเวอร์ชันนี้

หลักฐานยืนยันการรับเข้าจุดรับพัสดุ ไม่ใช่การยืนยันว่าเจ้าของมารับของแล้ว
ผู้ดูแลที่ล็อกอินเท่านั้นเปิด /evidence และดาวน์โหลดภาพผ่านเว็บได้ พร้อม Cache-Control: no-store
ภาพเก่าที่สร้างจาก main.py ยังอยู่ local และไม่ได้ย้ายเข้าเว็บโดยอัตโนมัติ
อย่าเปิด scanner local กับเว็บรับเลขเดียวกันพร้อมกัน เพราะเส้นทางเก่ายังไม่ได้ใช้ receipt transaction นี้

## ตั้งค่าและ deploy

เว็บต้องมี SECRET_KEY และ ADMIN_PASSWORD เมื่อรัน Flask/Gunicorn โดยตรง; serve_local.py สร้าง session secret ชั่วคราวและถามรหัสเมื่อจำเป็น
ใช้ FIREBASE_KEY_JSON หรือ FIREBASE_KEY_PATH สำหรับ service account
อย่า commit .env, firebase_key.json หรือภาพส่วนบุคคล

Render Blueprint: render.yaml (ยังไม่ได้ deploy)
- Build: pip install -r requirements.txt
- Start: gunicorn web_app:app --bind 0.0.0.0:$PORT
- Env: SECRET_KEY, ADMIN_PASSWORD, FIREBASE_KEY_JSON, TELEGRAM_BOT_TOKEN
- /health เป็น HTTP liveness เท่านั้น ไม่ได้ตรวจ Firebase/Telegram

## ตรวจสอบ

`python -m unittest discover -s tests -v`
ใช้ mock กับ Firebase/Telegram; ทดสอบตัวอ่านจริงด้วยภาพ Code128 และ QR ที่สร้างขึ้น
ทดสอบเบราว์เซอร์ด้วยข้อมูลสังเคราะห์ ไม่เขียนฐานข้อมูลจริงและไม่ส่งข้อความถึงสมาชิก

อ้างอิงกล้อง: https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia
อ้างอิงธุรกรรม: https://firebase.google.com/docs/firestore/manage-data/transactions
อ้างอิง deploy: https://render.com/docs/deploy-flask
