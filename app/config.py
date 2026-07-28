"""Конфигурация приложения через Pydantic Settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")
    SECRET_KEY: str = Field(default="change-me-in-production")
    WEBHOOK_SECRET: str = Field(default="change-me-in-production")
    AGENT_NAME: str = Field(default="Высокотехнологичный сотрудник Bestconsulting")

    # === LLM через OpenRouter (единый шлюз) ===
    OPENROUTER_API_KEY: str = Field(default="")
    OPENROUTER_BASE_URL: str = Field(default="https://openrouter.ai/api/v1")
    
    # Модели через OpenRouter
    OPENAI_MODEL: str = Field(default="openai/gpt-4o-mini")
    DEEPSEEK_MODEL: str = Field(default="deepseek/deepseek-chat")
    ANTHROPIC_MODEL: str = Field(default="anthropic/claude-sonnet-4-20250514")
    QWEN_MODEL: str = Field(default="qwen/qwen-coder-plus-latest")
    OPENAI_EMBEDDING_MODEL: str = Field(default="text-embedding-3-large")

    # === Каналы ===
    TELEGRAM_BOT_TOKEN: str = Field(default="")
    TELEGRAM_WEBHOOK_URL: str = Field(default="")
    MAX_API_TOKEN: str = Field(default="")
    MAX_API_URL: str = Field(default="https://api.max.ru/v1")
    EMAIL_USER: str = Field(default="")
    EMAIL_PASSWORD: str = Field(default="")
    EMAIL_SMTP_SERVER: str = Field(default="smtp.mail.ru")
    EMAIL_SMTP_PORT: int = Field(default=465)
    EMAIL_IMAP_SERVER: str = Field(default="imap.mail.ru")
    EMAIL_IMAP_PORT: int = Field(default=993)

    # === Google ===
    GOOGLE_CLIENT_ID: str = Field(default="")
    GOOGLE_CLIENT_SECRET: str = Field(default="")
    YOUTUBE_API_KEY: str = Field(default="")

    # === База данных ===
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./bestconsulting.db")
    DB_POOL_SIZE: int = Field(default=10)
    DB_MAX_OVERFLOW: int = Field(default=20)
    DB_ECHO: bool = Field(default=False)

    # === Кэш ===
    REDIS_URL: str = Field(default="")

    # === Мониторинг ===
    SENTRY_DSN: str = Field(default="")

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"


settings = Settings()
