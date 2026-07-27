# BestConsulting AI Core v2.0

> Единый ИИ-сотрудник компании Bestconsulting. Оркестратор, память, самообучение, мультиканальность.

## Статус

| Компонент | Статус |
|-----------|--------|
| FastAPI Foundation | 🚧 v2.0 |
| PostgreSQL + pgvector | ⬜ v2.1 |
| AI Orchestrator | ⬜ v2.2 |
| Memory & RAG | ⬜ v2.3 |
| Knowledge Base | ⬜ v2.4 |
| Channels (TG, MAX, Email) | ⬜ v2.5 |
| Enterprise (мониторинг, админка) | ⬜ v3.0 |

## Быстрый старт

```bash
# 1. Клонировать репозиторий
git clone <repo-url>
cd bestconsulting-ai-core

# 2. Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или: venv\Scripts\activate  # Windows

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Создать .env из примера
cp .env.example .env
# Отредактируй .env, добавь свои API-ключи

# 5. Запустить
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

- `GET /` — информация о сервисе
- `GET /api/v1/health/` — health check
- `GET /api/v1/health/ready` — readiness probe
- `POST /api/v1/chat/` — диалог с агентом (заглушка в v2.0)

## Архитектура

См. [docs/architecture.md](docs/architecture.md)

## Переменные окружения

Все секреты хранятся в `.env` (не загружается в Git).
См. `.env.example` для полного списка.

## Лицензия

Proprietary — Bestconsulting
