"""Зависимости (dependencies) для API endpoints."""
from typing import Generator

from app.config import settings


def get_settings():
    """Возвращает настройки приложения."""
    return settings
