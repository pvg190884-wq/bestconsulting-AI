"""Telegram Webhook — получение сообщений от Telegram."""
import httpx
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.services.telegram_service import send_message
from app.services.chat_service import ChatService
from app.services.file_extract_service import extract_text
from app.config import settings
from app.utils.logger import setup_logging

router = APIRouter()
logger = setup_logging()

TELEGRAM_API = "https://api.telegram.org/bot"


async def _download_telegram_file(file_id: str) -> tuple[bytes, str]:
    """Скачивает файл из Telegram по file_id. Возвращает (bytes, filename)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{TELEGRAM_API}{settings.TELEGRAM_BOT_TOKEN}/getFile", params={"file_id": file_id})
        data = r.json()
        if not data.get("ok"):
            raise ValueError(f"getFile failed: {data}")
        file_path = data["result"]["file_path"]
        real_filename = file_path.rsplit("/", 1)[-1]
        file_url = f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}/{file_path}"
        r2 = await client.get(file_url)
        r2.raise_for_status()
        return r2.content, real_filename


@router.post("/webhook")
async def telegram_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Принимает webhook от Telegram."""
    data = await request.json()

    if "message" not in data:
        return {"ok": True}

    msg = data["message"]
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    text = msg.get("text", "")

    if not chat_id:
        return {"ok": True}

    if text.startswith("/"):
        if text == "/start":
            await send_message(chat_id,
                "Здравствуйте! Я высокотехнологичный сотрудник Bestconsulting. "
                "Уточните, из какой вы организации и представьтесь?"
            )
            return {"ok": True}

    user_id = str(chat_id)
    service = ChatService()

    # --- Обработка файлов и фото ---
    document = msg.get("document")
    photos = msg.get("photo")

    file_id = None
    doc_filename = None

    if document:
        file_id = document.get("file_id")
        doc_filename = document.get("file_name") or "document"
    elif photos:
        largest = photos[-1]  # Telegram отдаёт массив размеров — берём самый большой
        file_id = largest.get("file_id")

    if file_id:
        try:
            content, real_filename = await _download_telegram_file(file_id)
            use_filename = doc_filename or real_filename
            extracted = await extract_text(content, use_filename, llm_service=service.llm)
            if not extracted:
                await send_message(chat_id, "Не удалось извлечь текст из файла. Поддерживаются: TXT, PDF, Excel, PowerPoint, JPG, PNG.")
                return {"ok": True}
            result = await service.process_file(db, user_id, "telegram", extracted, use_filename)
            await send_message(chat_id, result.get("response", "Файл обработан."))
        except Exception as e:
            logger.error(f"[TG] Ошибка обработки файла: {e}")
            await send_message(chat_id, "Ошибка при обработке файла. Попробуйте ещё раз.")
        return {"ok": True}

    if not text:
        return {"ok": True}

    result = await service.process_message(db, user_id, "telegram", text)
    response_text = result.get("response", "Ошибка обработки")
    await send_message(chat_id, response_text)

    return {"ok": True}
