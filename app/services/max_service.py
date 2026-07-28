"""MAX Service — отправка сообщений и установка webhook."""
import httpx
from app.config import settings
from app.utils.logger import setup_logging

logger = setup_logging()


async def send_max_message(chat_id: str, text: str):
    """Отправляет сообщение в MAX."""
    if not settings.MAX_API_TOKEN:
        logger.warning("[MAX] Токен не настроен")
        return False

    url = f"{settings.MAX_API_URL}/messages/send"
    payload = {
        "token": settings.MAX_API_TOKEN,
        "chat_id": chat_id,
        "text": text,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            logger.info(f"[MAX] Отправлено в чат {chat_id}")
            return True
    except Exception as e:
        logger.error(f"[MAX] Ошибка отправки: {e}")
        return False


async def set_max_webhook(webhook_url: str):
    """Устанавливает webhook для MAX."""
    if not settings.MAX_API_TOKEN:
        return False

    url = f"{settings.MAX_API_URL}/webhook/set"
    payload = {
        "token": settings.MAX_API_TOKEN,
        "url": webhook_url,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, json=payload)
            data = r.json()
            if data.get("ok"):
                logger.info(f"[MAX] Webhook установлен: {webhook_url}")
                return True
            else:
                logger.error(f"[MAX] Ошибка webhook: {data}")
                return False
    except Exception as e:
        logger.error(f"[MAX] Ошибка установки webhook: {e}")
        return False


async def delete_max_webhook():
    """Удаляет webhook MAX."""
    if not settings.MAX_API_TOKEN:
        return False

    url = f"{settings.MAX_API_URL}/webhook/delete"
    payload = {"token": settings.MAX_API_TOKEN}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            await client.post(url, json=payload)
            logger.info("[MAX] Webhook удалён")
    except Exception as e:
        logger.error(f"[MAX] Ошибка удаления webhook: {e}")
