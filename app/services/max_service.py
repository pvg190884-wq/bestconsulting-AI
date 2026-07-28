"""MAX Service — отправка сообщений и webhook."""
import httpx
from app.config import settings
from app.utils.logger import setup_logging

logger = setup_logging()

MAX_API_HOST = "https://platform-api2.max.ru"


async def send_max_message(chat_id: str | int, text: str):
    """Отправляет сообщение в MAX через API."""
    if not settings.MAX_API_TOKEN:
        logger.warning("[MAX] Токен не настроен")
        return False

    try:
        cid = int(chat_id)
    except (ValueError, TypeError):
        logger.error(f"[MAX] Неверный chat_id: {chat_id}")
        return False

    url = f"{MAX_API_HOST}/messages"
    payload = {"chat_id": cid, "text": text}
    headers = {
        "Authorization": settings.MAX_API_TOKEN,
        "Content-Type": "application/json",
    }

    try:
        # verify=False — только для этого запроса, обход SSL Минцифры
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            r = await client.post(url, json=payload, headers=headers)
            logger.info(f"[MAX] API ответ: {r.status_code} | {r.text[:200]}")
            if r.status_code == 200:
                logger.info(f"[MAX] Отправлено в чат {cid}")
                return True
            else:
                logger.error(f"[MAX] API ошибка: {r.status_code}")
                return False
    except Exception as e:
        logger.error(f"[MAX] Ошибка: {e}")
        return False


async def set_max_webhook(webhook_url: str):
    """Устанавливает webhook для MAX."""
    if not settings.MAX_API_TOKEN:
        return False

    url = f"{MAX_API_HOST}/webhook/set"
    payload = {"url": webhook_url}
    headers = {
        "Authorization": settings.MAX_API_TOKEN,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            r = await client.post(url, json=payload, headers=headers)
            data = r.json()
            if data.get("ok") or r.status_code == 200:
                logger.info(f"[MAX] Webhook OK: {webhook_url}")
                return True
            else:
                logger.error(f"[MAX] Webhook error: {data}")
                return False
    except Exception as e:
        logger.error(f"[MAX] Webhook exception: {e}")
        return False


async def delete_max_webhook():
    """Удаляет webhook MAX."""
    if not settings.MAX_API_TOKEN:
        return False

    url = f"{MAX_API_HOST}/webhook/delete"
    headers = {"Authorization": settings.MAX_API_TOKEN}
    try:
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            await client.post(url, headers=headers)
            logger.info("[MAX] Webhook удалён")
    except Exception as e:
        logger.error(f"[MAX] Delete error: {e}")
