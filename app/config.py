"""Конфигурация приложения через Pydantic Settings.
Все секреты загружаются из переменных окружения.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Настройки BestConsulting AI Core."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # === Основные ===
    APP_ENV: str = Field(default="development", description="production / development / testing")
    LOG_LEVEL: str = Field(default="INFO")
    SECRET_KEY: str = Field(default="change-me-in-production")
    WEBHOOK_SECRET: str = Field(default="change-me-in-production")
    AGENT_NAME: str = Field(default="Высокотехнологичный сотрудник Bestconsulting")

    # === LLM Провайдеры ===
    # KIMI (основной оркестратор)
    KIMI_API_KEY: str = Field(default="")
    KIMI_BASE_URL: str = Field(default="https://api.moonshot.ai/v1")
    KIMI_MODEL: str = Field(default="kimi-k2.6")

    # OpenAI (резерв / документы)
    OPENAI_API_KEY: str = Field(default="")
    OPENAI_BASE_URL: str = Field(default="https://api.openai.com/v1")
    OPENAI_MODEL: str = Field(default="gpt-5.5")

    # DeepSeek (аналитика / логика)
    DEEPSEEK_API_KEY: str = Field(default="")
    DEEPSEEK_BASE_URL: str = Field(default="https://api.deepseek.com/v1")
    DEEPSEEK_MODEL: str = Field(default="deepseek-chat")

    # Anthropic Claude (длинные документы)
    ANTHROPIC_API_KEY: str = Field(default="")
    ANTHROPIC_MODEL: str = Field(default="claude-sonnet-4-20250514")

    # Qwen (программирование)
    QWEN_API_KEY: str = Field(default="")
    QWEN_BASE_URL: str = Field(default="https://dashscope.aliyuncs.com/compatible-mode/v1")
    QWEN_MODEL: str = Field(default="qwen-coder-plus-latest")

    # === Каналы коммуникации ===
    # Telegram
    TELEGRAM_BOT_TOKEN: str = Field(default="")
    TELEGRAM_WEBHOOK_URL: str = Field(default="")

    # MAX (Мессенджер)
    MAX_API_TOKEN: str = Field(default="")
    MAX_API_URL: str = Field(default="https://api.max.ru/v1")

    # Email
    EMAIL_USER: str = Field(default="")
    EMAIL_PASSWORD: str = Field(default="")
    EMAIL_SMTP_SERVER: str = Field(default="smtp.mail.ru")
    EMAIL_SMTP_PORT: int = Field(default=465)
    EMAIL_IMAP_SERVER: str = Field(default="imap.mail.ru")
    EMAIL_IMAP_PORT: int = Field(default=993)

    # === Google / YouTube ===
    GOOGLE_CLIENT_ID: str = Field(default="")
    GOOGLE_CLIENT_SECRET: str = Field(default="")
    YOUTUBE_API_KEY: str = Field(default="")

    # === База данных ===
    DATABASE_URL: str = Field(default="sqlite:///./bestconsulting.db")

    # === Кэш / Очереди ===
    REDIS_URL: str = Field(default="")

    # === Мониторинг ===
    SENTRY_DSN: str = Field(default="")

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"


# Глобальный экземпляр настроек
settings = Settings()
