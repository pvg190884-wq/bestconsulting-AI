# BestConsulting AI Core — Архитектура v2.2

## GPT Orchestrator

GPT-5.5 — единый мозг. Принимает все сообщения, анализирует контекст, обращается к памяти, формирует ответ.

### Fallback-цепочка
```
GPT (OpenAI) → DeepSeek → Claude → Qwen → "Техобслуживание"
```

### Память (v2.2 — база, v2.3 — RAG)
- **Диалоговая**: история текущего разговора (PostgreSQL)
- **Клиентская**: предпочтения, история обращений
- **Глобальная**: база знаний компании (knowledge_items)

### Самообучение (v2.4)
```
Диалог клиента
    │
    ▼
GPT анализирует — стоит ли запомнить?
    │
    ▼
ДА → Создать Knowledge Item
    │
    ▼
Векторизация (OpenAI Embeddings)
    │
    ▼
PostgreSQL + pgvector
    │
    ▼
При следующем запросе: RAG-retrieval
```

## Дорожная карта

| Версия | Фокус | Статус |
|--------|-------|--------|
| v2.0 Foundation | FastAPI, структура | ✅ |
| v2.1 Database | PostgreSQL, Alembic | ✅ |
| v2.2 GPT Orchestrator | Live API, fallback, память | ✅ |
| v2.3 Memory | pgvector, RAG | ⬜ |
| v2.4 Knowledge | Самообучение, ночная обработка | ⬜ |
| v2.5 Channels | Telegram, MAX, Email | ⬜ |
| v3.0 Enterprise | Админка, мониторинг, очереди | ⬜ |
