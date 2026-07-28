"""Email Service — отправка уведомлений (неблокирующая)."""
import asyncio
import smtplib
import ssl
from concurrent.futures import ThreadPoolExecutor
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings
from app.utils.logger import setup_logging

logger = setup_logging()

ADMIN_EMAIL = "thebestconsulting@mail.ru"

# Пул потоков для SMTP (не блокирует async event loop)
_email_executor = ThreadPoolExecutor(max_workers=2)


def _send_sync(subject: str, body: str, to_email: str) -> tuple[bool, str]:
    """Синхронная отправка через SMTP."""
    try:
        logger.info(f"[Email] Подключение к {settings.EMAIL_SMTP_SERVER}:{settings.EMAIL_SMTP_PORT}")
        
        msg = MIMEMultipart()
        msg["From"] = settings.EMAIL_USER
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(
            settings.EMAIL_SMTP_SERVER, 
            settings.EMAIL_SMTP_PORT, 
            context=context, 
            timeout=5
        ) as server:
            logger.info("[Email] Соединение установлено, логин...")
            server.login(settings.EMAIL_USER, settings.EMAIL_PASSWORD)
            logger.info("[Email] Авторизация OK, отправка...")
            server.sendmail(settings.EMAIL_USER, to_email, msg.as_string())
            logger.info("[Email] Письмо отправлено")
        return True, ""
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"[Email] Ошибка авторизации: {e}")
        return False, "Auth failed"
    except smtplib.SMTPServerDisconnected as e:
        logger.error(f"[Email] Сервер разорвал соединение: {e}")
        return False, "Server disconnected"
    except Exception as e:
        logger.error(f"[Email] Ошибка: {type(e).__name__}: {e}")
        return False, str(e)[:200]


async def send_email_notification(subject: str, body: str, to_email: str = None):
    """Асинхронная отправка через ThreadPoolExecutor."""
    if not settings.EMAIL_USER or not settings.EMAIL_PASSWORD:
        logger.warning("[Email] SMTP не настроен")
        return False

    to = to_email or ADMIN_EMAIL
    loop = asyncio.get_event_loop()
    
    try:
        # run_in_executor — надёжнее asyncio.to_thread
        result, error = await asyncio.wait_for(
            loop.run_in_executor(_email_executor, _send_sync, subject, body, to),
            timeout=10.0
        )
        if result:
            logger.info(f"[Email] Успешно отправлено на {to}")
        else:
            logger.error(f"[Email] Не отправлено: {error}")
        return result
    except asyncio.TimeoutError:
        logger.error("[Email] Таймаут 10 сек")
        return False
    except Exception as e:
        logger.error(f"[Email] Исключение: {e}")
        return False


def format_escalation_email(esc_id: str, client_id: str, reason: str, context: str, contacts: str) -> str:
    """Форматирует тело письма."""
    return f"""
УВЕДОМЛЕНИЕ ОБ ЭСКАЛАЦИИ

ID: {esc_id}
Клиент: {client_id}
Причина: {reason}

Потребность:
{context}

Контакты:
{contacts}

---
BestConsulting AI Core
"""
