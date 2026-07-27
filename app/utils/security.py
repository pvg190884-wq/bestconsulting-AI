"""Утилиты безопасности."""
import hmac
import hashlib
import secrets
from app.config import settings

def verify_webhook_signature(payload: bytes, signature: str, secret: str = None) -> bool:
    secret = secret or settings.WEBHOOK_SECRET
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

def generate_id() -> str:
    return secrets.token_urlsafe(16)
