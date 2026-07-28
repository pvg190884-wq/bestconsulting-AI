"""Telegram Service — отправка сообщений и установка webhook."""
import httpx
from app.config import settings
from app.utils.logger import setup_logging

logger = setup_logging()

TELEGRAM_API = "https://api.telegram.org/bot"


async def send_message(chat_id: int, text: str):
    """Отправляет сообщение в Telegram."""
    url = f"{TELEGRAM_API}{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            logger.info(f"[TG] Отправлено сообщение в чат {chat_id}")
    except Exception as e:
        logger.error(f"[TG] Ошибка отправки: {e}")


async def set_webhook(webhook_url: str):
    """Устанавливает webhook для бота."""
    url = f"{TELEGRAM_API}{settings.TELEGRAM_BOT_TOKEN}/setWebhook"
    payload = {
        "url": webhook_url,
        "allowed_updates": ["message"],
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, json=payload)
            data = r.json()
            if data.get("ok"):
                logger.info(f"[TG] Webhook установлен: {webhook_url}")
                return True
            else:
                logger.error(f"[TG] Ошибка установки webhook: {data}")
                return False
    except Exception as e:
        logger.error(f"[TG] Ошибка установки webhook: {e}")
        return False


async def delete_webhook():
    """Удаляет webhook (для отладки)."""
    url = f"{TELEGRAM_API}{settings.TELEGRAM_BOT_TOKEN}/deleteWebhook"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            await client.get(url)
            logger.info("[TG] Webhook удалён")
    except Exception as e:
        logger.error(f"[TG] Ошибка удаления webhook: {e}")
