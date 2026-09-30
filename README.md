# AI-слепки

Локальное веб-приложение, которое превращает локальные директории в маленькие машиночитаемые
JSON-«слепки» с помощью локальных LLM (**Ollama** или **LM Studio**) и даёт поиск по этой библиотеке.

- FastAPI + Jinja2 + Tailwind CSS 4 (CDN) + Alpine.js (CDN)
- SQLite + FTS5 (с fallback на `LIKE`)
- генерация: сбор файлов → очистка текста → chunking → LLM → JSON → проверка цитат → сохранение
- без версий слепка: одна директория + один тип = один слепок (замена без истории)
- без Meilisearch / Docker / облака — всё локально

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Приложение: <http://127.0.0.1:8000>

## Страницы

| Маршрут | Назначение |
|---|---|
| `/` | Главная: статистика, статус провайдера, последние слепки |
| `/create` | Создание слепка с прогрессом и заменой существующего |
| `/templates` | CRUD шаблонов, включение, default, тест промпта |
| `/search` | Поиск и фильтры (тип, провайдер, модель, шаблон, confidence, возраст) |
| `/snapshots/{id}` | Детали: Overview / Facts / Highlights / Entities / Metadata / Raw JSON |
| `/settings` | Провайдер, параметры генерации, активные шаблоны по типам |

## API

```
GET    /api/health
GET    /api/stats
GET    /api/meta
GET    /api/settings            PUT /api/settings
POST   /api/providers/test
GET    /api/models
GET    /api/templates           POST /api/templates
GET    /api/templates/{id}      PUT /api/templates/{id}    DELETE /api/templates/{id}
POST   /api/templates/{id}/default
POST   /api/templates/{id}/enabled?enabled=true
POST   /api/templates/{id}/test
POST   /api/snapshots
GET    /api/snapshots/exists?directory=&snapshot_type=
GET    /api/snapshots?query=&type=&provider=&model=&template_id=&min_confidence=&max_age_days=&limit=&offset=
GET    /api/snapshots/{id}      GET /api/snapshots/{id}/raw   DELETE /api/snapshots/{id}
GET    /api/jobs/{job_id}
GET    /api/files?directory=
```

## Данные

```
data/
  snapshots.db        # settings, templates, snapshots, jobs, snapshots_fts
  snapshots/*.json    # сами слепки (обычно 1–10 КБ)
```

Каталог можно перенести переменной окружения `SHOT_DATA_DIR`.

## Настройка

Перед первым запуском откройте **Настройки**: выберите `ollama` (`http://localhost:11434`) или
`lmstudio` (`http://localhost:1234/v1`), укажите модель и проверьте соединение.

Шесть встроенных шаблонов (article / documentation / news / forum / notes / general)
создаются автоматически при первом запуске.

## Тесты

```bash
pip install pytest
pytest -q
```
