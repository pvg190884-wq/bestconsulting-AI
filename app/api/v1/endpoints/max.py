"""MAX Service — получение webhook и отправка сообщений в МАХ."""
import httpx
import traceback
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.chat_service import ChatService
from app.services.file_extract_service import extract_text
from app.config import settings
from app.utils.logger import setup_logging

logger = setup_logging()
router = APIRouter()

_chat_service = None
def _get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service


MAX_API_HOST = "https://platform-api2.max.ru"


async def send_max_message(chat_id, text: str) -> bool:
    if not text or not chat_id:
        return False
    try:
        cid = int(chat_id)
    except (ValueError, TypeError):
        logger.error(f"[MAX] Неверный chat_id: {chat_id}")
        return False

    url = f"{MAX_API_HOST}/messages?chat_id={cid}"
    payload = {"text": text[:4000]}
    headers = {
        "Authorization": settings.MAX_API_TOKEN,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
            r = await client.post(url, headers=headers, json=payload)
            if r.status_code == 200:
                logger.info(f"[MAX] Сообщение отправлено в чат {cid}")
                return True
            else:
                logger.error(f"[MAX] Ошибка {r.status_code}: {r.text[:200]}")
                return False
    except Exception as e:
        logger.error(f"[MAX] Ошибка отправки: {e}")
        return False


async def send_max_document(chat_id, file_bytes: bytes, filename: str) -> bool:
    try:
        cid = int(chat_id)
    except (ValueError, TypeError):
        logger.error(f"[MAX] Неверный chat_id для файла: {chat_id}")
        return False

    headers = {"Authorization": settings.MAX_API_TOKEN}

    try:
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            r1 = await client.get(f"{MAX_API_HOST}/uploads", params={"type": "file"}, headers=headers)
            r1.raise_for_status()
            upload_url = r1.json().get("url")
            if not upload_url:
                logger.error(f"[MAX] Не удалось получить upload-URL: {r1.text[:200]}")
                return False

            files = {"data": (filename, file_bytes)}
            r2 = await client.post(upload_url, files=files)
            r2.raise_for_status()
            upload_result = r2.json()
            token = upload_result.get("token") or (upload_result.get("photos", {}) or {}).get("token")
            if not token:
                logger.error(f"[MAX] Не удалось получить token загрузки: {r2.text[:300]}")
                return False

            payload = {"attachments": [{"type": "file", "payload": {"token": token}}]}
            r3 = await client.post(
                f"{MAX_API_HOST}/messages?chat_id={cid}",
                headers={**headers, "Content-Type": "application/json"},
                json=payload,
            )
            if r3.status_code == 200:
                logger.info(f"[MAX] Файл {filename} отправлен в чат {cid}")
                return True
            else:
                logger.error(f"[MAX] Ошибка отправки файла: {r3.status_code} {r3.text[:200]}")
                return False
    except Exception as e:
        logger.error(f"[MAX] Ошибка отправки файла: {e}")
        return False


async def _download_max_attachment(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.content


async def _fetch_message_by_id(message_id: str) -> dict | None:
    """Получает сообщение по ID — нужно, когда пользователь отвечает (reply)
    на ранее отправленный файл: MAX кладёт в текущее сообщение только
    ссылку {type: 'reply', mid: ...}, без самого содержимого."""
    headers = {"Authorization": settings.MAX_API_TOKEN}
    try:
        async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
            r = await client.get(f"{MAX_API_HOST}/messages/{message_id}", headers=headers)
            if r.status_code == 200:
                return r.json()
            else:
                logger.warning(f"[MAX] Не удалось получить сообщение {message_id}: {r.status_code} {r.text[:200]}")
                return None
    except Exception as e:
        logger.error(f"[MAX] Ошибка получения сообщения по ID: {e}")
        return None


@router.post("/webhook")
async def max_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        data = await request.json()
        logger.debug(f"[MAX] Raw webhook: {data}")

        message = data.get("message", {}) if isinstance(data, dict) else {}

        if message.get("sender", {}).get("is_bot"):
            return {"ok": True, "skipped": "bot"}

        sender_id = str(
            message.get("sender", {}).get("user_id")
            or data.get("user_id")
            or data.get("from", {}).get("id")
            or ""
        ).strip()

        chat_id = (
            message.get("recipient", {}).get("chat_id")
            or data.get("chat", {}).get("id")
            or sender_id
        )

        if not sender_id or not chat_id:
            logger.warning(f"[MAX] Нет sender_id/chat_id в webhook: {data}")
            return {"ok": True}

        body = message.get("body", {}) or {}
        message_text = (body.get("text") or data.get("text") or data.get("body") or "").strip()
        attachments = body.get("attachments") or []

        # --- Поддержка "Reply" на ранее отправленный файл ---
        # MAX кладёт в текущее сообщение только ссылку {type: 'reply', mid: '...'},
        # без содержимого исходного сообщения — нужно подтянуть его отдельным запросом
        if not attachments:
            link = message.get("link", {}) or {}
            if link.get("type") == "reply" and link.get("mid"):
                original = await _fetch_message_by_id(link["mid"])
                if original:
                    original_body = original.get("body", {}) or {}
                    original_attachments = original_body.get("attachments") or []
                    if original_attachments:
                        attachments = original_attachments
                        # текст текущего сообщения (reply) играет роль подписи к файлу

        service = _get_chat_service()

        if attachments:
            att = attachments[0]
            att_type = att.get("type")
            payload = att.get("payload", {}) or {}
            file_url = payload.get("url")
            filename = att.get("filename") or ("photo.jpg" if att_type == "image" else "file")

            if file_url:
                try:
                    content = await _download_max_attachment(file_url)
                    extracted = await extract_text(content, filename, llm_service=service.llm)
                    if not extracted:
                        await send_max_message(chat_id, "Не удалось извлечь текст из файла. Поддерживаются: TXT, PDF, Excel, PowerPoint, JPG, PNG.")
                        return {"ok": True}
                    result = await service.process_file(db, sender_id, "max", extracted, filename, caption=message_text)
                    response_text = result.get("response", "Ошибка обработки")
                    await send_max_message(chat_id, response_text)
                    file_bytes = result.get("file_bytes")
                    gen_filename = result.get("filename")
                    if file_bytes and gen_filename:
                        await send_max_document(chat_id, file_bytes, gen_filename)
                except Exception as e:
                    logger.error(f"[MAX] Ошибка обработки вложения: {e}")
                    await send_max_message(chat_id, "Ошибка при обработке файла. Попробуйте ещё раз.")
            else:
                logger.warning(f"[MAX] Вложение без payload.url: {att}")
            return {"ok": True}

        if not message_text:
            return {"ok": True}

        logger.info(f"[MAX] Входящее от {sender_id} (chat {chat_id}): {message_text[:100]}...")

        result = await service.process_message(db, sender_id, "max", message_text)

        if isinstance(result, dict) and result.get("response"):
            await send_max_message(chat_id, result["response"])
            file_bytes = result.get("file_bytes")
            gen_filename = result.get("filename")
            if file_bytes and gen_filename:
                await send_max_document(chat_id, file_bytes, gen_filename)

        return {"ok": True}
    except Exception as e:
        err = traceback.format_exc()
        logger.error(f"[MAX] Критическая ошибка webhook: {err}")
        return {"ok": True}


@router.get("/health")
async def max_health():
    return {"status": "ok", "service": "max"}
