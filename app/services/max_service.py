"""MAX Service — отправка сообщений через API @MasterBot."""
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

    url = f"{MAX_API_HOST}/messages?chat_id={chat_id}"
    payload = {"text": text}
    headers = {
        "Authorization": settings.MAX_API_TOKEN,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            r = await client.post(url, json=payload, headers=headers)
            logger.info(f"[MAX] API ответ: {r.status_code} | {r.text[:200]}")
            if r.status_code == 200:
                logger.info(f"[MAX] Отправлено в чат {chat_id}")
                return True
            else:
                logger.error(f"[MAX] API ошибка: {r.status_code} | {r.text[:300]}")
                return False
    except Exception as e:
        logger.error(f"[MAX] Ошибка: {e}")
        return False
