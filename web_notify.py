import asyncio
from telegram import Bot
from config import TELEGRAM_BOT_TOKEN
from receipt_store import claim_notification, finish_notification


async def send_receipt(record):
    if not TELEGRAM_BOT_TOKEN or not record.get("telegram_chat_id"):
        return False
    message = (f"📦 รับพัสดุเข้าจุดรับของแล้ว\n\nผู้รับ: {record['member_name']}\n"
               f"เลขพัสดุ: {record['tracking_no']}\nเวลา: {record['scanned_at']}\n\n"
               "ระบบบันทึกภาพหลักฐานแล้ว กรุณาติดต่อรับพัสดุที่จุดรับพัสดุของหอพัก")
    try:
        async with Bot(token=TELEGRAM_BOT_TOKEN) as bot:
            await bot.send_message(chat_id=record["telegram_chat_id"], text=message,
                                   connect_timeout=5, read_timeout=10, write_timeout=10)
        return True
    except Exception:
        # Do not log URLs, tokens, or recipient details.
        return False


def notify_receipt(identifier):
    record, claim = claim_notification(identifier)
    if claim is None:
        return bool(record.get("notified"))
    success = asyncio.run(send_receipt(record))
    finish_notification(identifier, claim, success)
    return success
