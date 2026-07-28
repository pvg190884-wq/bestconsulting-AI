"""Email Service — отправка уведомлений через SMTP."""
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings
from app.utils.logger import setup_logging

logger = setup_logging()

ADMIN_EMAIL = "thebestconsulting@mail.ru"  # ← Получатель уведомлений


def send_email_notification(subject: str, body: str, to_email: str = None):
    """Отправляет email-уведомление."""
    if not settings.EMAIL_USER or not settings.EMAIL_PASSWORD:
        logger.warning("[Email] Не настроены учётные данные SMTP")
        return False

    to = to_email or ADMIN_EMAIL  # По умолчанию thebestconsulting@mail.ru

    msg = MIMEMultipart()
    msg["From"] = settings.EMAIL_USER
    msg["To"] = to
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(settings.EMAIL_SMTP_SERVER, settings.EMAIL_SMTP_PORT, context=context) as server:
            server.login(settings.EMAIL_USER, settings.EMAIL_PASSWORD)
            server.sendmail(settings.EMAIL_USER, to, msg.as_string())
        logger.info(f"[Email] Уведомление отправлено на {to}: {subject}")
        return True
    except Exception as e:
        logger.error(f"[Email] Ошибка отправки: {e}")
        return False


def format_escalation_email(esc_id: str, client_id: str, reason: str, context: str, contacts: str) -> str:
    """Форматирует тело письма об эскалации."""
    return f"""
УВЕДОМЛЕНИЕ ОБ ЭСКАЛАЦИИ

ID: {esc_id}
Клиент: {client_id}
Причина: {reason}

Потребность клиента:
{context}

Контакты для связи:
{contacts}

---
Сообщение сгенерировано автоматически.
BestConsulting AI Core
"""
