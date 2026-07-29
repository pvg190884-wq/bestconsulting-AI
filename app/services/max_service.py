"""MAX Service — отправка сообщений и управление подписками."""
import httpx
from app.config import settings
from app.utils.logger import setup_logging

logger = setup_logging()

MAX_API_HOST = "https://platform-api2.max.ru"


async def send_max_message(chat_id: int, text: str):
    """Отправляет сообщение в MAX. chat_id в query-параметре, text в body."""
    if not settings.MAX_API_TOKEN:
        logger.warning("[MAX] Токен не настроен")
        return False

    try:
        cid = int(chat_id)
    except (ValueError, TypeError):
        logger.error(f"[MAX] Неверный chat_id: {chat_id}")
        return False

    url = f"{MAX_API_HOST}/messages?chat_id={cid}"
    payload = {"text": text}
    headers = {
        "Authorization": settings.MAX_API_TOKEN,
        "Content-Type": "application/json",
    }

    try:
        # verify=False — обход SSL Минцифры (сертификат не доверенен за пределами РФ)
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            r = await client.post(url, json=payload, headers=headers)
            logger.info(f"[MAX] API ответ: {r.status_code} | {r.text[:200]}")
            if r.status_code == 200:
                logger.info(f"[MAX] Сообщение отправлено в чат {cid}")
                return True
            else:
                logger.error(f"[MAX] API ошибка: {r.status_code} | {r.text[:300]}")
                return False
    except Exception as e:
        logger.error(f"[MAX] Ошибка отправки: {e}")
        return False


async def subscribe_webhook(webhook_url: str):
    """Создаёт подписку на webhook через правильный endpoint MAX API (POST /subscriptions)."""
    if not settings.MAX_API_TOKEN:
        logger.warning("[MAX] Токен не настроен")
        return False

    url = f"{MAX_API_HOST}/subscriptions"
    payload = {"url": webhook_url}
    headers = {
        "Authorization": settings.MAX_API_TOKEN,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            r = await client.post(url, json=payload, headers=headers)
            data = r.json() if r.text else {}
            logger.info(f"[MAX] Подписка: {r.status_code} | {data}")
            if r.status_code in (200, 201) or data.get("success") is True:
                logger.info(f"[MAX] Подписка создана: {webhook_url}")
                return True
            else:
                logger.error(f"[MAX] Ошибка подписки: {data}")
                return False
    except Exception as e:
        logger.error(f"[MAX] Ошибка создания подписки: {e}")
        return False


async def list_subscriptions():
    """Возвращает список активных подписок (GET /subscriptions)."""
    if not settings.MAX_API_TOKEN:
        return []

    url = f"{MAX_API_HOST}/subscriptions"
    headers = {"Authorization": settings.MAX_API_TOKEN}

    try:
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            r = await client.get(url, headers=headers)
            if r.status_code == 200:
                return r.json()
            else:
                logger.warning(f"[MAX] Список подписок: {r.status_code}")
                return []
    except Exception as e:
        logger.error(f"[MAX] Ошибка получения подписок: {e}")
        return []


async def unsubscribe_webhook(webhook_url: str):
    """Удаляет подписку на webhook (DELETE /subscriptions?url=...)."""
    if not settings.MAX_API_TOKEN:
        return False

    url = f"{MAX_API_HOST}/subscriptions?url={webhook_url}"
    headers = {"Authorization": settings.MAX_API_TOKEN}

    try:
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            r = await client.delete(url, headers=headers)
            logger.info(f"[MAX] Удаление подписки: {r.status_code}")
            return r.status_code in (200, 204)
    except Exception as e:
        logger.error(f"[MAX] Ошибка удаления подписки: {e}")
        return False
