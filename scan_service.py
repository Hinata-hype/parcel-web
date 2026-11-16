"""Decode the submitted frame itself and preserve a bounded JPEG as evidence."""
from datetime import datetime, timedelta, timezone
from io import BytesIO
import re
import warnings

from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError
import zxingcpp

MAX_UPLOAD = 5 * 1024 * 1024
MAX_PIXELS = 16_000_000
MAX_EVIDENCE = 450_000


def normalize_tracking(value):
    value = re.sub(r"\s+", "", value).upper()
    return value if re.fullmatch(r"[A-Z0-9-]{4,64}", value) else None


def decode_frame(raw):
    if not raw or len(raw) > MAX_UPLOAD:
        raise ValueError("ภาพต้องมีขนาดไม่เกิน 5 MB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("รองรับภาพ JPEG, PNG และ WebP เท่านั้น")
                if source.width * source.height > MAX_PIXELS:
                    raise ValueError("ภาพใหญ่เกินไป กรุณาใช้ภาพไม่เกิน 16 ล้านพิกเซล")
                image = ImageOps.exif_transpose(source).convert("RGB")
                image.thumbnail((1920, 1920))
        codes = sorted({code for result in zxingcpp.read_barcodes(image)
                        if (code := normalize_tracking(result.text))})
        return image, codes
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise ValueError("อ่านไฟล์ภาพไม่ได้ กรุณาถ่ายใหม่") from exc


def make_evidence(image, tracking, scanned_at):
    image = image.copy()
    image.thumbnail((1280, 1280))
    # Put the timestamp outside the original frame so it cannot hide the label.
    evidence = Image.new("RGB", (max(600, image.width), image.height + 54), "#142b3b")
    evidence.paste(image, (0, 0))
    draw = ImageDraw.Draw(evidence)
    draw.text((12, image.height + 8), f"Tracking: {tracking}", fill="white")
    draw.text((12, image.height + 28), f"Received: {scanned_at} | Web camera / photo", fill="white")
    for quality in (85, 70, 55, 40):
        output = BytesIO()
        evidence.save(output, format="JPEG", quality=quality, optimize=True)
        if len(output.getvalue()) <= MAX_EVIDENCE:
            return output.getvalue()
    raise ValueError("ภาพหลักฐานมีขนาดใหญ่เกินไป กรุณาถ่ายใหม่")


def now_bangkok():
    return datetime.now(timezone(timedelta(hours=7))).isoformat(timespec="seconds")
