# BestConsulting AI Core — Архитектура v2.0

## Концепция
Единый ИИ-сотрудник компании Bestconsulting. Оркестратор, который сам решает — ответить сам или привлечь специализированные модели. Пользователь всегда общается только с единым агентом, не замечая сложной инфраструктуры.

## Компоненты

### 1. API Layer (`app/api/`)
FastAPI роутеры. Версионирование API (v1, v2...). Endpoints: health, chat, admin, upload.

### 2. Orchestrator (`app/orchestrator/`)
AI Router — определяет тип задачи и выбирает LLM. Fallback-цепочка при сбоях.

### 3. Services (`app/services/`)
- `llm_service.py` — унифицированный интерфейс к LLM
- `embedding_service.py` — векторизация текста

### 4. Memory (`app/memory/`)
Долговременная память на PostgreSQL + pgvector:
- Глобальная (компания)
- Проектная
- Клиентская
- Диалоговая

### 5. Cache (`app/cache/`)
Redis / in-memory кэш. Семантический кэш для снижения затрат.

### 6. Models (`app/models/`)
Pydantic модели для валидации данных.

### 7. Prompts (`app/prompts/`)
Системные промпты, хранящиеся в файлах (не в коде). Меняются без деплоя.

### 8. Utils (`app/utils/`)
Логирование, безопасность, хелперы.

## Дорожная карта

| Версия | Фокус | Статус |
|--------|-------|--------|
| v2.0 Foundation | FastAPI, структура, health | 🚧 |
| v2.1 Database | PostgreSQL, Alembic, модели | ⬜ |
| v2.2 AI | OpenAI Responses API, оркестратор | ⬜ |
| v2.3 Memory | pgvector, RAG, история | ⬜ |
| v2.4 Knowledge | База знаний, самообучение | ⬜ |
| v2.5 Channels | Telegram, MAX, Email, Web | ⬜ |
| v3.0 Enterprise | Мониторинг, очереди, админка | ⬜ |

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

## Память и самообучение
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
