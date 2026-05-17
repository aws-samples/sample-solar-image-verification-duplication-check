import io
import json
import math
from datetime import datetime, timezone

from PIL import Image


def build_response(status_code: int, body: dict) -> dict:
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,OPTIONS',
        },
        'body': json.dumps(body, default=str),
    }


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def get_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_jpeg_bytes(image_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ('RGBA', 'P', 'LA'):
        img = img.convert('RGB')
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=92)
    return buf.getvalue()


def normalize_name(name: str) -> str:
    if not name:
        return ''
    return ''.join(c for c in name.lower() if c.isalnum() or c.isspace()).strip()


def name_similarity(a: str, b: str) -> float:
    a, b = normalize_name(a), normalize_name(b)
    if not a or not b:
        return 0.0
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)
