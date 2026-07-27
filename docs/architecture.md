# BestConsulting AI Core — Архитектура v2.1

## Дорожная карта

| Версия | Фокус | Статус |
|--------|-------|--------|
| v2.0 Foundation | FastAPI, структура, health | ✅ |
| v2.1 Database | PostgreSQL, Alembic, модели | ✅ |
| v2.2 AI | OpenAI Responses API, оркестратор | ⬜ |
| v2.3 Memory | pgvector, RAG, история | ⬜ |
| v2.4 Knowledge | База знаний, самообучение | ⬜ |
| v2.5 Channels | Telegram, MAX, Email, Web | ⬜ |
| v3.0 Enterprise | Мониторинг, очереди, админка | ⬜ |

## Схема БД v2.1

```
clients
├── id (PK)
├── external_id (уникальный, индекс)
├── name, email, phone
├── channel (telegram/max/email/web)
├── preferences (JSON)
└── created_at, updated_at

chat_sessions
├── id (PK)
├── client_id (FK → clients)
├── channel
├── status (active/closed/archived)
├── metadata (JSON)
└── created_at, updated_at

chat_messages
├── id (PK)
├── session_id (FK → chat_sessions)
├── role (user/assistant/system)
├── content
├── model_used
├── tokens_used
├── latency_ms
├── metadata (JSON)
└── created_at

knowledge_items
├── id (PK)
├── type (document/faq/scenario/instruction/client_preference/learned)
├── title
├── content
├── tags (JSON)
├── source
├── confidence
├── verified
├── embedding (JSON, заготовка под pgvector)
├── metadata (JSON)
└── created_at, updated_at
```

## Модельная независимость
```
Запрос клиента
    │
    ▼
Orchestrator (KIMI / GPT)
    │
    ├──► KIMI — общение, сценарии
    ├──► GPT — документы, универсальное
    ├──► DeepSeek — аналитика, логика
    ├──► Claude — длинные документы
    ├──► Qwen — код, программирование
    │
    ▼
Aggregator — единый стиль
    │
    ▼
Ответ клиенту
```

## Память и самообучение (v2.3–v2.4)
```
Диалог клиента
    │
    ▼
Анализ полезности (LLM)
    │
    ▼
Извлечь знания
    │
    ▼
Векторизация
    │
    ▼
PostgreSQL + pgvector
    │
    ▼
При следующем запросе: RAG-retrieval
```

## Отказоустойчивость
```
KIMI → GPT → DeepSeek → Claude → Qwen → Локальная Llama → "Техобслуживание"
```
