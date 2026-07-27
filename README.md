# BestConsulting AI Core v2.1

> Единый ИИ-сотрудник компании Bestconsulting. Оркестратор, память, самообучение, мультиканальность.

## Статус

| Компонент | Статус |
|-----------|--------|
| FastAPI Foundation | ✅ v2.0 |
| PostgreSQL + Alembic | ✅ v2.1 |
| AI Orchestrator | ⬜ v2.2 |
| Memory & RAG (pgvector) | ⬜ v2.3 |
| Knowledge Base | ⬜ v2.4 |
| Channels (TG, MAX, Email) | ⬜ v2.5 |
| Enterprise | ⬜ v3.0 |

## Быстрый старт

```bash
# 1. Клонировать
git clone <repo-url>
cd bestconsulting-ai-core

# 2. Окружение
python -m venv venv
source venv/bin/activate  # или venv\Scripts\activate
pip install -r requirements.txt

# 3. .env
cp .env.example .env
# Отредактируй .env, добавь API-ключи

# 4. Миграции БД (для PostgreSQL)
alembic upgrade head

# 5. Запуск
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

- `GET /` — информация о сервисе
- `GET /api/v1/health/` — health check
- `GET /api/v1/health/ready` — readiness (с проверкой БД)
- `POST /api/v1/chat/` — диалог с агентом

## База данных

v2.1 добавляет 4 таблицы:
- `clients` — клиенты (Telegram ID, MAX ID, email)
- `chat_sessions` — сессии диалогов
- `chat_messages` — сообщения с метаданными (модель, токены, latency)
- `knowledge_items` — база знаний (заготовка под pgvector)

## Переменные окружения

Все секреты в `.env` (не в Git). См. `.env.example`.

## Лицензия

Proprietary — Bestconsulting


