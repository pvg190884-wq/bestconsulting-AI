# BestConsulting AI Core v2.2

> Единый ИИ-сотрудник Bestconsulting. GPT-оркестратор, память, самообучение, мультиканальность.

## Статус

| Компонент | Статус |
|-----------|--------|
| FastAPI Foundation | ✅ v2.0 |
| PostgreSQL + Alembic | ✅ v2.1 |
| GPT Orchestrator + Live API | ✅ v2.2 |
| Memory & RAG (pgvector) | ⬜ v2.3 |
| Knowledge Base + Self-learning | ⬜ v2.4 |
| Channels (TG, MAX, Email) | ⬜ v2.5 |
| Enterprise (admin, monitoring) | ⬜ v3.0 |

## Архитектура v2.2

```
Пользователь
    │
    ▼
FastAPI (Railway)
    │
    ├──► Chat Service
    │       │
    │       ├──► Dialog Manager (PostgreSQL)
    │       │       ├──► История диалога
    │       │       └──► Контекст клиента
    │       │
    │       ├──► LLM Service
    │       │       ├──► OpenAI GPT (основной)
    │       │       ├──► DeepSeek (fallback)
    │       │       ├──► Claude (fallback)
    │       │       └──► Qwen (fallback)
    │       │
    │       └──► Сохранение в БД
    │
    └──► Admin API (заготовка)
```

## API Endpoints

- `GET /` — информация о сервисе
- `GET /api/v1/health/` — health check
- `GET /api/v1/health/ready` — readiness
- `POST /api/v1/chat/` — диалог с GPT-агентом (живой!)
- `GET /api/v1/admin/stats` — статистика (заготовка)

## Переменные окружения

Все секреты в `.env` (не в Git). См. `.env.example`.

## Лицензия

Proprietary — Bestconsulting
