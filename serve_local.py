"""Interactive localhost launcher. Production still uses gunicorn web_app:app."""
import getpass
import secrets
import web_app


def main():
    if not web_app.app.secret_key or web_app.app.secret_key == 'change-this-before-deploy':
        web_app.app.secret_key = secrets.token_hex(32)
    while not web_app.ADMIN_PASSWORD:
        web_app.ADMIN_PASSWORD = getpass.getpass('ตั้งรหัสผ่านเข้าเว็บ (ไม่แสดงตัวอักษรขณะพิมพ์): ').strip()
        if not web_app.ADMIN_PASSWORD:
            print('กรุณาพิมพ์รหัสผ่านก่อนกด Enter')
    print('เปิดเว็บ: http://127.0.0.1:5000/scan')
    print('เปิดหน้าต่างนี้ค้างไว้ กด Ctrl+C เพื่อหยุดเว็บ')
    web_app.app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()
