
## User:

**Files:** AI-слепки как локальные модели Ollama превращают веб-сайты и статьи в маленькие файлы и как строить на этом собственный поиск.md, Местные ИИ-слепки как Ollama превращает статьи и сайты в маленькие файлы и становится локальным поиском.md


## Model:

Ниже — подробное задание, которое можно передать AI-разработчику. Оно уже учитывает оба исходных текста, но адаптировано под твои ограничения: **локальное приложение**, **FastAPI + venv + Tailwind CSS CDN**, **светлый UI**, **без версий слепков**, **без Meilisearch**, **по папке**, **типы слепков**, **шаблоны**, **поиск/выдача**, **настройки Ollama/LM Studio**.

---

## Задание для AI: создать локальное веб-приложение “AI-слепки”

Ты — опытный Python/Fullstack-разработчик.  
Твоя задача — создать **локальное веб-приложение** на **FastAPI** для генерации маленьких машиночитаемых “AI-слепков” из локальных директорий с помощью локальных LLM: **Ollama** или **LM Studio**.

Приложение должно быть:

- **локальным**;
- **светлым и красивым**;
- работать в **venv**;
- использовать **Tailwind CSS через CDN**;
- хранить данные локально;
- **не использовать Meilisearch**;
- **не хранить версии слепков**;
- позволять пользователю указывать **директорию**, **тип слепка**, создавать слепок, сохранять его в библиотеку, искать по библиотеке и настраивать генерацию.

---

# 1. Контекст из исходных текстов

Из двух исходных текстов следует общая идея:

- обычные веб-страницы, статьи, документы, форумы и заметки часто слишком тяжелые и шумные;
- локальная LLM может превратить большой текст в **маленький структурированный файл-слепок**;
- слепок должен быть не просто “кратко”, а **машиночитаемым**, **структурированным**, **проверяемым**;
- внутри слепа должны быть:
  - краткое резюме;
  - ключевые факты;
  - цитаты, подтверждающие факты;
  - темы/теги/сущности;
  - вопросы;
  - оценка уверенности;
  - метаданные о модели, шаблоне, дате, источнике;
- такие слепки можно использовать как **локальную библиотеку знаний** и **поиск по смыслам**;
- поиск может строиться поверх маленьких JSON-файлов, а не по полным страницам;
- для локального прототипа достаточно:
  - FastAPI;
  - SQLite;
  - файловых JSON-слепков;
  - SQLite FTS5 для поиска;
  - локальной LLM.

Важно: в исходных текстах упоминаются централизованные серверы, S3, Postgres, Meilisearch, Qdrant, версии, модерация, подписи узлов.  
**В нашем приложении это НЕ требуется.**

Мы делаем **простой локальный прототип**:

- один пользователь;
- один локальный компьютер;
- локальные директории;
- локальные модели;
- локальная база;
- локальный поиск;

---

# 2. Цель приложения

Создать локальное веб-приложение, которое позволяет:

1. **Указать локальную директорию**, по которой нужно создать слепок.
2. **Указать тип слепка**:
   - `article`
   - `documentation`
   - `news`
   - `forum`
   - `notes`
   - `general`
3. **Создать слепок** с помощью выбранной локальной модели:
   - Ollama
   - LM Studio
4. **Сохранить слепок** в локальную библиотеку:
   - JSON-файл;
   - запись в SQLite;
   - запись в SQLite FTS5.
5. **Искать** по библиотеке слепков:
   - по запросу;
   - по типу;
   - по модели;
   - по шаблону;
   - по минимальной уверенности;
   - по дате.
6. **Просматривать** детально:
   - резюме;
   - факты;
   - цитаты;
   - теги;
   - сущности;
   - вопросы;
   - raw JSON;
   - метаданные.
7. **Создавать и сохранять шаблоны слепков**:
   - каждый шаблон привязан к типу или нескольким типам;
   - содержит system prompt;
   - содержит user prompt;
   - содержит JSON-схему;
   - может быть включен/выключен;
   - может быть по умолчанию для типа.
8. **Настраивать параметры**:
   - провайдер: Ollama / LM Studio;
   - base URL;
   - модель;
   - temperature;
   - top_p;
   - seed;
   - max_tokens;
   - timeout;
   - лимиты размера текста;
   - JSON mode;
   - выбор активного шаблона для каждого типа.

---

# 3. Жесткие требования

## 3.1. Стек

Использовать:

- Python 3.14+
- `venv`
- `FastAPI`
- `uvicorn[standard]`
- `pydantic` v2
- `httpx`
- `jinja2`
- `python-multipart`
- `beautifulsoup4`
- `lxml`
- `pypdf` — опционально, если нужна поддержка PDF
- Tailwind CSS через CDN
- Alpine.js через CDN — для интерактивности
- SQLite
- SQLite FTS5

Не использовать:

- Meilisearch
- Elasticsearch
- Typesense
- Postgres
- S3
- MinIO
- Qdrant
- Weaviate
- Milvus
- Docker
- внешний облачный LLM API
- версионирование слепков
- централизованный кластер
- систему подписи узлов
- сложные очереди, если не требуется

---

## 3.2. Ограничения

Приложение должно:

- работать локально;
- запускаться в venv;
- использовать только локальные модели;
- хранить все данные локально;
- не отправлять данные в облако;
- не сохранять историю версий слепков;
- при повторном создании слепа для той же директории и того же типа:
  - **заменять** существующий слепок;
  - **не создавать** новую версию;
  - **не хранить** старый вариант.

---

# 4. Запуск проекта

Проект должен запускаться так:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

После запуска приложение доступно по адресу:

```bash
http://127.0.0.1:8000
```

`requirements.txt` должен содержать минимум:

```txt
fastapi
uvicorn[standard]
pydantic
httpx
jinja2
python-multipart
beautifulsoup4
lxml
pypdf
```

---

# 5. Рекомендуемая структура проекта

Создать проект со структурой:

```bash
project/
  .venv/
  requirements.txt
  README.md
  app/
    __init__.py
    main.py
    config.py
    database.py
    models.py
    schemas.py
    services/
      __init__.py
      llm_provider.py
      text_extractor.py
      snapshot_generator.py
      snapshot_search.py
      template_service.py
      settings_service.py
    api/
      __init__.py
      routes.py
    templates/
      base.html
      index.html
      create.html
      templates.html
      search.html
      snapshot_detail.html
      settings.html
    static/
      css/
      js/
  data/
    snapshots/
    snapshots.db
  tests/
    test_json_parser.py
    test_quote_verification.py
    test_search.py
    test_templates.py
    test_llm_provider.py
```

---

# 6. Архитектура приложения

Приложение состоит из:

1. **Frontend**:
   - Jinja2 templates;
   - Tailwind CSS CDN;
   - Alpine.js;
   - простые страницы;
   - polling для фоновых задач.

2. **Backend**:
   - FastAPI;
   - REST API;
   - SQLite;
   - background tasks;
   - provider abstraction для Ollama/LM Studio.

3. **Хранение**:
   - `data/snapshots.db` — SQLite;
   - `data/snapshots/` — JSON-файлы слепков;
   - FTS5-таблица для поиска.

4. **Генерация**:
   - чтение файлов из директории;
   - очистка текста;
   - chunking;
   - вызов локальной LLM;
   - парсинг JSON;
   - проверка цитат;
   - сохранение JSON;
   - обновление SQLite и FTS.

---

# 7. Модель данных

## 7.1. Таблица `settings`

Хранит текущие настройки приложения.

Поля:

```sql
CREATE TABLE IF NOT EXISTS settings (
  id INTEGER PRIMARY KEY,
  provider TEXT NOT NULL DEFAULT 'ollama',
  base_url TEXT NOT NULL,
  api_key TEXT NOT NULL DEFAULT '',
  model TEXT NOT NULL,
  temperature REAL NOT NULL DEFAULT 0.1,
  top_p REAL NOT NULL DEFAULT 0.9,
  seed INTEGER NOT NULL DEFAULT 42,
  max_tokens INTEGER NOT NULL DEFAULT 2000,
  timeout_seconds INTEGER NOT NULL DEFAULT 300,
  json_mode INTEGER NOT NULL DEFAULT 1,
  max_input_chars INTEGER NOT NULL DEFAULT 12000,
  max_chunk_chars INTEGER NOT NULL DEFAULT 6000,
  default_templates_json TEXT NOT NULL DEFAULT '{}',
  updated_at TEXT NOT NULL
);
```

`provider` принимает значения:

- `ollama`
- `lmstudio`

`default_templates_json` — JSON-объект вида:

```json
{
  "article": 1,
  "documentation": 2,
  "news": 3,
  "forum": 4,
  "notes": 5,
  "general": 6
}
```

То есть для каждого типа хранится ID активного шаблона.

---

## 7.2. Таблица `templates`

Хранит шаблоны генерации слепков.

Поля:

```sql
CREATE TABLE IF NOT EXISTS templates (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  snapshot_type TEXT NOT NULL,
  system_prompt TEXT NOT NULL,
  user_prompt TEXT NOT NULL,
  chunk_user_prompt TEXT NOT NULL DEFAULT '',
  merge_user_prompt TEXT NOT NULL DEFAULT '',
  schema_json TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  is_default INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

`snapshot_type` принимает значения:

- `article`
- `documentation`
- `news`
- `forum`
- `notes`
- `general`

`schema_json` — JSON Schema или просто JSON-шаблон, который требует модель.

---

## 7.3. Таблица `snapshots`

Хранит метаданные и основные поля слепков.

```sql
CREATE TABLE IF NOT EXISTS snapshots (
  id INTEGER PRIMARY KEY,
  snapshot_id TEXT NOT NULL UNIQUE,
  directory_path TEXT NOT NULL,
  normalized_directory TEXT NOT NULL,
  snapshot_type TEXT NOT NULL,
  template_id INTEGER,
  template_name TEXT,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  error TEXT,
  title TEXT,
  summary TEXT,
  sections_json TEXT NOT NULL DEFAULT '[]',
  facts_json TEXT NOT NULL DEFAULT '[]',
  highlights_json TEXT NOT NULL DEFAULT '[]',
  entities_json TEXT NOT NULL DEFAULT '{}',
  questions_json TEXT NOT NULL DEFAULT '[]',
  tags_json TEXT NOT NULL DEFAULT '[]',
  confidence REAL NOT NULL DEFAULT 0.0,
  content_hash TEXT,
  original_chars INTEGER NOT NULL DEFAULT 0,
  snapshot_chars INTEGER NOT NULL DEFAULT 0,
  file_count INTEGER NOT NULL DEFAULT 0,
  files_json TEXT NOT NULL DEFAULT '[]',
  content_truncated INTEGER NOT NULL DEFAULT 0,
  search_text TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

Сделать уникальный индекс:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_snapshots_directory_type
ON snapshots(normalized_directory, snapshot_type);
```

Это обеспечивает требование **“без версий”**:

- одна директория + один тип = один слепок;
- при повторном создании запись заменяется;
- старые варианты не сохраняются.

---

## 7.4. Таблица `jobs`

Для отслеживания длительной генерации.

```sql
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY,
  snapshot_type TEXT NOT NULL,
  directory_path TEXT NOT NULL,
  template_id INTEGER,
  status TEXT NOT NULL DEFAULT 'pending',
  progress INTEGER NOT NULL DEFAULT 0,
  step TEXT NOT NULL DEFAULT 'queued',
  error TEXT,
  snapshot_id TEXT,
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT
);
```

`status` принимает значения:

- `pending`
- `processing`
- `success`
- `failed`

`step` может быть:

- `queued`
- `checking_directory`
- `collecting_files`
- `extracting_text`
- `generating`
- `parsing_json`
- `verifying_quotes`
- `saving`
- `done`

---

## 7.5. FTS5-таблица

Для поиска использовать SQLite FTS5.

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS snapshots_fts
USING fts5(
  snapshot_id,
  title,
  directory,
  search_text,
  summary,
  facts_text,
  tags_text,
  questions_text
);
```

При сохранении слепа:

- удалить старую запись из FTS по `snapshot_id`;
- вставить новую.

При удалении слепа:

- удалить запись из FTS;
- удалить JSON-файл;
- удалить запись из `snapshots`.

---

# 8. Формат AI-слепа

Каждый слепок должен быть маленьким JSON-файлом, обычно 1–10 КБ.

Файл сохраняется в:

```bash
data/snapshots/{snapshot_id}.json
```

Формат:

```json
{
  "id": "snap-a1b2c3d4e5f6",
  "directory": "/home/user/docs",
  "title": "Документация по Ollama",
  "type": "documentation",
  "fetched_at": "2026-01-15T10:00:00Z",
  "summary": "Краткое описание директории и основных тем.",
  "sections": [
    {
      "heading": "Основное",
      "text": "Краткий текст секции."
    }
  ],
  "facts": [
    {
      "id": "f1",
      "claim": "Ollama позволяет запускать локальные LLM.",
      "quote": "Ollama — популярный способ запускать локальные LLM",
      "file": "README.md",
      "confidence": 0.9,
      "type": "verified",
      "verified": true
    }
  ],
  "highlights": [
    {
      "quote": "Локальные LLM помогают сохранить приватность данных",
      "file": "privacy.md",
      "reason": "Ключевая идея о приватности"
    }
  ],
  "entities": {
    "topics": ["LLM", "поиск", "приватность"],
    "organizations": ["Ollama"],
    "people": [],
    "technologies": ["JSON", "SQLite"],
    "locations": [],
    "dates": ["2026"]
  },
  "questions": [
    "Что такое Ollama?",
    "Зачем нужны локальные LLM?"
  ],
  "tags": ["ollama", "local-llm", "search", "privacy"],
  "confidence": 0.82,
  "provider": "ollama",
  "model": "llama3.1:8b",
  "template_id": 1,
  "template_name": "Article Snapshot",
  "content_hash": "sha256:abc123",
  "original_chars": 182340,
  "snapshot_chars": 1840,
  "file_count": 12,
  "files": ["README.md", "guide.md"],
  "content_truncated": false,
  "search_text": "Ollama локальные LLM приватность поиск JSON SQLite"
}
```

---

# 9. Правила идентификации слепа

`snapshot_id` должен быть стабильным и основываться **только** на:

- normalized directory
- snapshot type

Например:

```python
snapshot_id = "snap-" + sha256(normalized_directory + ":" + snapshot_type).hexdigest()[:16]
```

Это означает:

- для одной директории и одного типа существует один слепок;
- при повторной генерации он заменяется;
- версии не сохраняются.

`content_hash` может меняться, если контент изменился, но это не создает новую версию.

---

# 10. Типы слепков

Поддерживаемые типы:

- `article`
- `documentation`
- `news`
- `forum`
- `notes`
- `general`

Для каждого типа должен быть хотя бы один включенный шаблон.

Если для выбранного типа нет активного шаблона:

- показать понятную ошибку;
- предложить перейти на страницу шаблонов;
- не начинать генерацию.

---

# 11. Провайдеры LLM

Нужно реализовать абстракцию провайдера.

## 11.1. Ollama

По умолчанию:

```text
http://localhost:11434
```

Использовать endpoint:

```bash
POST {base_url}/api/chat
```

Payload:

```json
{
  "model": "llama3.1:8b",
  "messages": [
    {"role": "system", "content": "system prompt"},
    {"role": "user", "content": "user prompt"}
  ],
  "stream": false,
  "options": {
    "temperature": 0.1,
    "top_p": 0.9,
    "seed": 42,
    "num_predict": 2000
  }
}
```

Ответ содержит:

```json
{
  "message": {
    "content": "..."
  }
}
```

Для проверки доступности использовать:

```bash
GET {base_url}/api/tags
```

## 11.2. LM Studio

По умолчанию:

```text
http://localhost:1234/v1
```

Если пользователь ввел `http://localhost:1234`, приложение должно автоматически добавить `/v1`, если его нет.

Использовать OpenAI-compatible endpoint:

```bash
POST {base_url}/chat/completions
```

Payload:

```json
{
  "model": "llama3.1:8b",
  "messages": [
    {"role": "system", "content": "system prompt"},
    {"role": "user", "content": "user prompt"}
  ],
  "temperature": 0.1,
  "top_p": 0.9,
  "seed": 42,
  "max_tokens": 2000,
  "stream": false,
  "response_format": {
    "type": "json_object"
  }
}
```

Если `response_format` не поддерживается конкретной версией LM Studio, приложение должно:

- не падать;
- просто отправлять запрос без `response_format`;
- полагаться на строгий prompt и парсинг JSON.

Для проверки доступности использовать:

```bash
GET {base_url}/models
```

---

# 12. Требования к промптам

Шаблон должен содержать:

- `system_prompt`
- `user_prompt`
- опционально `chunk_user_prompt`
- опционально `merge_user_prompt`
- `schema_json`

## 12.1. Базовый system prompt

Создать встроенные шаблоны по умолчанию.

Базовый system prompt:

```text
Ты создаешь AI-слепок — маленький машиночитаемый JSON-файл.

Верни только один валидный JSON-объект.
Не возвращай markdown, пояснения, комментарии или текст вне JSON.

Правила:
1. Используй только предоставленный текст.
2. Не добавляй знания извне.
3. Не выдумывай факты.
4. Каждое fact должно содержать поле quote — точную цитату из исходного текста.
5. Если информации нет, используй пустые списки или null.
6. summary должен быть кратким и нейтральным.
7. confidence — от 0.0 до 1.0.
8. Если текст рекламный, неполный или шумный, снижай confidence.
9. search_text — строка для поиска, состоящая из title, summary, tags, topics, technologies и ключевых claims.
```

## 12.2. User prompt

Шаблон user prompt должен содержать плейсхолдеры:

- `{type}`
- `{directory}`
- `{files}`
- `{text}`
- `{chunk_index}`
- `{chunk_count}`
- `{partials}`

Пример:

```text
Сформируй AI-слепок.

Тип: {type}
Директория: {directory}
Файлы: {files}

Исходный текст:
{text}

Верни строго JSON по схеме:
{schema}
```

## 12.3. Chunk prompt

Если исходный текст больше `max_input_chars`, нужно разбить его на части.

Chunk user prompt:

```text
Суммаризируй только этот фрагмент текста.

Тип: {type}
Директория: {directory}
Фрагмент {chunk_index} из {chunk_count}

Текст:
{text}

Верни JSON:
{
  "summary": "...",
  "facts": [
    {
      "id": "c1",
      "claim": "...",
      "quote": "...",
      "file": "...",
      "confidence": 0.0,
      "type": "verified|inferred|opinion"
    }
  ],
  "highlights": [
    {
      "quote": "...",
      "file": "...",
      "reason": "..."
    }
  ],
  "entities": {
    "topics": [],
    "organizations": [],
    "people": [],
    "technologies": [],
    "locations": [],
    "dates": []
  },
  "questions": [],
  "tags": [],
  "confidence": 0.0
}
```

## 12.4. Merge prompt

Если было несколько фрагментов, нужен merge prompt.

```text
Даны частичные слепки:

{partials}

Объедини их в один финальный AI-слепок.

Правила:
1. Используй только предоставленные частичные данные.
2. Удали дублирующиеся факты.
3. Сохрани только важные и проверяемые факты.
4. Каждая цитата должна существовать в исходном тексте.
5. Верни финальный JSON по схеме:
{schema}
```

---

# 13. Встроенные шаблоны по умолчанию

При первом запуске создать шаблоны:

1. `Article Snapshot`
   - type: `article`
   - default: true

2. `Documentation Snapshot`
   - type: `documentation`
   - default: true

3. `News Snapshot`
   - type: `news`
   - default: true

4. `Forum Snapshot`
   - type: `forum`
   - default: true

5. `Notes Snapshot`
   - type: `notes`
   - default: true

6. `General Snapshot`
   - type: `general`
   - default: true

Для каждого шаблона задать `schema_json` с нужным форматом.

Пример JSON Schema:

```json
{
  "type": "object",
  "required": [
    "title",
    "summary",
    "facts",
    "highlights",
    "entities",
    "questions",
    "tags",
    "confidence"
  ],
  "properties": {
    "title": {"type": "string"},
    "summary": {"type": "string"},
    "sections": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["heading", "text"],
        "properties": {
          "heading": {"type": "string"},
          "text": {"type": "string"}
        }
      }
    },
    "facts": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "claim", "quote", "confidence", "type"],
        "properties": {
          "id": {"type": "string"},
          "claim": {"type": "string"},
          "quote": {"type": "string"},
          "file": {"type": "string"},
          "confidence": {"type": "number"},
          "type": {
            "type": "string",
            "enum": ["verified", "inferred", "opinion"]
          }
        }
      }
    },
    "highlights": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["quote"],
        "properties": {
          "quote": {"type": "string"},
          "file": {"type": "string"},
          "reason": {"type": "string"}
        }
      }
    },
    "entities": {
      "type": "object",
      "required": ["topics", "organizations", "people", "technologies", "locations", "dates"],
      "properties": {
        "topics": {"type": "array", "items": {"type": "string"}},
        "organizations": {"type": "array", "items": {"type": "string"}},
        "people": {"type": "array", "items": {"type": "string"}},
        "technologies": {"type": "array", "items": {"type": "string"}},
        "locations": {"type": "array", "items": {"type": "string"}},
        "dates": {"type": "array", "items": {"type": "string"}}
      }
    },
    "questions": {"type": "array", "items": {"type": "string"}},
    "tags": {"type": "array", "items": {"type": "string"}},
    "confidence": {"type": "number"}
  }
}
```

---

# 14. Логика создания слепа

Пользователь на странице “Создание” вводит:

- директорию;
- тип.

После нажатия “Создать слепок”:

1. Frontend вызывает:

```bash
POST /api/snapshots
```

Payload:

```json
{
  "directory": "/home/user/articles",
  "snapshot_type": "article",
  "max_files": 200,
  "max_chars": 12000
}
```

2. Backend:
   - валидирует директорию;
   - проверяет, что это директория;
   - нормализует путь;
   - находит активный шаблон для типа;
   - создает job;
   - запускает background task.

3. Background task:
   - обновляет `jobs.progress` и `jobs.step`;
   - собирает файлы;
   - извлекает текст;
   - очищает текст;
   - делит на фрагменты, если нужно;
   - вызывает LLM;
   - парсит JSON;
   - валидирует JSON;
   - проверяет цитаты;
   - сохраняет JSON;
   - обновляет SQLite;
   - обновляет FTS;
   - устанавливает job.status = success.

---

# 15. Обработка директории

## 15.1. Какие файлы читать

По умолчанию читать:

- `.md`
- `.markdown`
- `.txt`
- `.rst`
- `.csv`
- `.json`
- `.yaml`
- `.yml`
- `.html`
- `.htm`

Опционально:

- `.pdf`, если установлен `pypdf`

## 15.2. Какие файлы пропускать

Пропускать:

- скрытые файлы и директории: `.git`, `.venv`, `.cache`, `.DS_Store`
- `node_modules`
- `__pycache__`
- `dist`
- `build`
- binary-файлы
- файлы больше 10 МБ
- файлы, которые невозможно прочитать как UTF-8

## 15.3. Очистка текста

Нужно:

- нормализовать пробелы;
- удалять лишние переносы;
- для HTML удалять:
  - `script`
  - `style`
  - `nav`
  - `footer`
  - `aside`
  - `form`
  - `noscript`
  - `svg`
- извлекать основной контент:
  - `article main`
  - `main`
  - `article`
  - `body`
- сохранять заголовок, если он есть;
- сохранять имя файла;
- сохранять относительный путь файла внутри директории.

---

# 16. Проверка цитат

Каждый fact должен иметь `quote`.

После получения JSON от модели нужно:

1. Нормализовать исходный текст:
   - lower case;
   - collapse whitespace.

2. Для каждого fact:
   - нормализовать quote;
   - проверить, содержится ли quote в исходном тексте;
   - если да:
     - `verified = true`
   - если нет:
     - `verified = false`
     - снизить `confidence` на 0.2;
     - если confidence стало меньше 0.3:
       - пометить fact как `low_quality`
       - но не удалять автоматически, чтобы пользователь мог посмотреть.

3. Для highlights:
   - проверить quote;
   - если не найдена:
     - `verified = false`

4. В UI показывать:
   - зеленый бейдж `verified`
   - серый/amber бейдж `unverified`

---

# 17. Парсинг ответа модели

Модель может вернуть:

```text
```json
{...}
```
```

или просто:

```text
{...}
```

или текст с лишними комментариями.

Нужно robust parser:

1. Убрать whitespace.
2. Убрать markdown-обвязку:
   - ```json
   - ```
3. Найти первый `{` и последний `}`.
4. Попробовать `json.loads`.
5. Если не удалось:
   - повторить генерацию до 2 раз;
   - во втором промпте явно указать:
     - “Верни только JSON”
     - “Не добавляй markdown”
     - “Не добавляй пояснения”
6. Если все равно не удалось:
   - job.status = failed
   - сохранить error message.

---

# 18. API

Реализовать endpoints:

## 18.1. Health

```bash
GET /api/health
```

Ответ:

```json
{
  "status": "ok",
  "provider": "ollama",
  "model": "llama3.1:8b",
  "provider_reachable": true,
  "model_available": true,
  "snapshot_count": 42,
  "template_count": 6
}
```

## 18.2. Settings

```bash
GET /api/settings
```

Возвращает текущие настройки.

```bash
PUT /api/settings
```

Обновляет настройки.

Payload:

```json
{
  "provider": "ollama",
  "base_url": "http://localhost:11434",
  "api_key": "",
  "model": "llama3.1:8b",
  "temperature": 0.1,
  "top_p": 0.9,
  "seed": 42,
  "max_tokens": 2000,
  "timeout_seconds": 300,
  "json_mode": true,
  "max_input_chars": 12000,
  "max_chunk_chars": 6000,
  "default_templates": {
    "article": 1,
    "documentation": 2,
    "news": 3,
    "forum": 4,
    "notes": 5,
    "general": 6
  }
}
```

## 18.3. Provider test

```bash
POST /api/providers/test
```

Payload:

```json
{
  "provider": "ollama",
  "base_url": "http://localhost:11434",
  "api_key": "",
  "model": "llama3.1:8b"
}
```

Ответ:

```json
{
  "reachable": true,
  "model_available": true,
  "models": ["llama3.1:8b", "qwen2.5:7b"],
  "error": null
}
```

## 18.4. Templates

```bash
GET /api/templates
```

Опциональные фильтры:

```bash
GET /api/templates?snapshot_type=article&enabled=true
```

```bash
POST /api/templates
```

Payload:

```json
{
  "name": "Article Snapshot",
  "description": "Шаблон для статей",
  "snapshot_type": "article",
  "system_prompt": "...",
  "user_prompt": "...",
  "chunk_user_prompt": "...",
  "merge_user_prompt": "...",
  "schema_json": "{...}",
  "enabled": true,
  "is_default": true
}
```

```bash
GET /api/templates/{id}
```

```bash
PUT /api/templates/{id}
```

```bash
DELETE /api/templates/{id}
```

Перед удалением проверить:

- если шаблон используется в `settings.default_templates_json`;
- показать предупреждение.

## 18.5. Template test

```bash
POST /api/templates/{id}/test
```

Payload:

```json
{
  "sample_text": "Ollama позволяет запускать локальные LLM.",
  "directory": "/home/user/test",
  "type": "article"
}
```

Ответ:

```json
{
  "success": true,
  "raw_output": "...",
  "parsed_json": {
    "title": "...",
    "summary": "..."
  },
  "error": null
}
```

## 18.6. Create snapshot

```bash
POST /api/snapshots
```

Payload:

```json
{
  "directory": "/home/user/articles",
  "snapshot_type": "article",
  "max_files": 200,
  "max_chars": 12000
}
```

Ответ:

```json
{
  "job_id": 123,
  "snapshot_id": "snap-a1b2c3d4e5f6"
}
```

## 18.7. Jobs

```bash
GET /api/jobs/{job_id}
```

Ответ:

```json
{
  "id": 123,
  "status": "processing",
  "progress": 45,
  "step": "generating",
  "error": null,
  "snapshot_id": "snap-a1b2c3d4e5f6",
  "created_at": "2026-01-15T10:00:00Z",
  "started_at": "2026-01-15T10:00:05Z",
  "finished_at": null
}
```

## 18.8. Snapshots

```bash
GET /api/snapshots
```

Параметры:

```text
query
type
provider
model
template_id
min_confidence
max_age_days
limit
offset
```

Пример:

```bash
GET /api/snapshots?query=ollama privacy&type=article&min_confidence=0.7&limit=20
```

Ответ:

```json
{
  "total": 12,
  "items": [
    {
      "snapshot_id": "snap-a1b2c3d4e5f6",
      "title": "Приватность локальных LLM",
      "directory": "/home/user/articles",
      "type": "article",
      "summary": "Статья описывает...",
      "confidence": 0.82,
      "provider": "ollama",
      "model": "llama3.1:8b",
      "template_name": "Article Snapshot",
      "tags": ["ollama", "privacy"],
      "updated_at": "2026-01-15T10:00:00Z"
    }
  ]
}
```

## 18.9. Snapshot detail

```bash
GET /api/snapshots/{snapshot_id}
```

Возвращает полный объект слепа.

## 18.10. Raw JSON

```bash
GET /api/snapshots/{snapshot_id}/raw
```

Возвращает JSON-файл.

## 18.11. Delete snapshot

```bash
DELETE /api/snapshots/{snapshot_id}
```

Действия:

- удалить запись из `snapshots`;
- удалить запись из FTS;
- удалить JSON-файл;
- если есть связанные jobs, пометить их как `cancelled` или удалить.

---

# 19. Страницы приложения

Все страницы должны быть:

- светлыми;
- чистыми;
- современными;
- адаптивными;
- использовать Tailwind CDN;
- использовать Alpine.js;
- иметь верхнюю навигацию.

Навигация:

- Главная
- Создание
- Шаблоны
- Поиск
- Настройки

Дизайн:

- фон: `bg-gray-50`
- карточки: `bg-white shadow rounded-xl border border-gray-100`
- основной цвет: `bg-blue-600`
- success: `bg-green-100 text-green-800`
- warning: `bg-amber-100 text-amber-800`
- error: `bg-red-100 text-red-800`
- info: `bg-blue-100 text-blue-800`
- бейджи: `rounded-full px-3 py-1 text-sm`
- кнопки: `px-4 py-2 rounded-lg`
- поля: `w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500`

---

# 20. Страница “Главная”

Маршрут:

```bash
GET /
```

На странице:

1. Заголовок:
   - “AI-слепки”

2. Подзаголовок:
   - “Локальная библиотека сжатых машиночитаемых конспектов”

3. Карточки статистики:
   - Всего слепков
   - Успешных
   - Ошибочных
   - По типам

4. Статус провайдера:
   - Ollama / LM Studio
   - доступен / недоступен
   - выбранная модель
   - кнопка “Тест соединения”

5. Последние 5 слепков:
   - title
   - directory
   - type badge
   - confidence
   - updated_at

6. Быстрые действия:
   - “Создать слепок”
   - “Открыть поиск”
   - “Управлять шаблонами”
   - “Настройки”

---

# 21. Страница “Создание”

Маршрут:

```bash
GET /create
```

На странице:

## 21.1. Форма

Поля:

- `directory`
  - label: “Директория”
  - placeholder: `/home/user/articles`
  - hint: “Укажите локальную папку, по которой нужно создать слепок”
- `snapshot_type`
  - select:
    - `article`
    - `documentation`
    - `news`
    - `forum`
    - `notes`
    - `general`
- `max_files`
  - optional number
  - default: 200
- `max_chars`
  - optional number
  - default: значение из settings

Кнопка:

- “Создать слепок”

## 21.2. Предупреждение

Если для выбранной директории и типа уже есть слепок:

показать:

```text
Для этой директории и типа уже существует слепок.
При создании он будет заменен без сохранения старой версии.
```

## 21.3. Прогресс

После отправки формы:

- показать прогресс-бар;
- показывать step:
  - “Очередь”
  - “Проверка директории”
  - “Сбор файлов”
  - “Очистка текста”
  - “Генерация”
  - “Проверка JSON”
  - “Проверка цитат”
  - “Сохранение”
  - “Готово”

Polling:

- каждые 2 секунды;
- `GET /api/jobs/{job_id}`

## 21.4. Результат

Если успех:

показать карточку:

- title
- directory
- type
- confidence
- file_count
- snapshot_chars
- verified facts count
- unverified facts count
- кнопки:
  - “Открыть”
  - “Скачать JSON”
  - “Искать”

Если ошибка:

показать:

- error message
- кнопку “Повторить”

---

# 22. Страница “Шаблоны”

Маршрут:

```bash
GET /templates
```

На странице:

## 22.1. Список шаблонов

Таблица или карточки:

- name
- type badge
- enabled
- is_default
- description
- updated_at
- actions:
  - Edit
  - Test
  - Enable/Disable
  - Set default
  - Delete

## 22.2. Создание шаблона

Кнопка:

- “Новый шаблон”

Форма:

- name
- description
- snapshot_type
- system_prompt
- user_prompt
- chunk_user_prompt
- merge_user_prompt
- schema_json
- enabled
- is_default

## 22.3. Редактирование

При редактировании:

- если шаблон используется в `default_templates`;
- показывать предупреждение:
  - “Этот шаблон используется как активный для типа X”

## 22.4. Проверка шаблона

Кнопка:

- “Проверить”

Форма:

- sample_text
- directory
- type

Результат:

- raw output
- parsed JSON
- validation status
- error

## 22.5. Удаление

При удалении:

- если шаблон default:
  - спросить подтверждение;
  - предложить выбрать другой шаблон для этого типа.

---

# 23. Страница “Поиск”

Маршрут:

```bash
GET /search
```

На странице:

## 23.1. Поисковая строка

- input:
  - placeholder: “Например: ollama privacy RAG”
- кнопка:
  - “Найти”

Debounced search:
- 300 мс после остановки ввода.

## 23.2. Фильтры

- type:
  - all
  - article
  - documentation
  - news
  - forum
  - notes
  - general
- provider:
  - all
  - ollama
  - lmstudio
- model:
  - all
  - dynamic list
- template:
  - all
  - list of templates
- min_confidence:
  - slider 0.0–1.0
- max_age_days:
  - number input

Кнопки:
- “Применить”
- “Сбросить”

## 23.3. Результаты

Список карточек:

- title
- directory
- type badge
- provider
- model
- template_name
- confidence bar
- updated_at
- summary
- tags
- verified facts count
- buttons:
  - “Открыть”
  - “Скачать JSON”

Пустое состояние:

```text
Ничего не найдено.
Попробуйте изменить запрос или фильтры.
```

## 23.4. Pagination

- previous
- next
- page number
- total count

---

# 24. Страница “Детали слепа”

Маршрут:

```bash
GET /snapshots/{snapshot_id}
```

На странице:

## 24.1. Header

- title
- directory
- type badge
- provider
- model
- template_name
- fetched_at
- updated_at
- confidence badge
- content_truncated badge

Кнопки:
- “Скачать JSON”
- “Удалить”

## 24.2. Tabs

### Overview

- summary
- sections
- questions
- tags

### Facts

Таблица:

- id
- claim
- quote
- file
- confidence
- type
- verified badge

### Highlights

- quote
- file
- reason
- verified badge

### Entities

- topics
- organizations
- people
- technologies
- locations
- dates

### Metadata

- snapshot_id
- provider
- model
- template_id
- content_hash
- original_chars
- snapshot_chars
- file_count
- files list

### Raw JSON

- preformatted JSON
- copy button
- download button

---

# 25. Страница “Настройки”

Маршрут:

```bash
GET /settings
```

На странице:

## 25.1. Provider

Select:

- Ollama
- LM Studio

Поля:

- base_url
- api_key
- model

Кнопка:

- “Тест соединения”

При тесте:

- показать:
  - reachable
  - model available
  - list of models

## 25.2. Параметры генерации

- temperature
- top_p
- seed
- max_tokens
- timeout_seconds
- json_mode
- max_input_chars
- max_chunk_chars

## 25.3. Активные шаблоны по типам

Для каждого типа:

- select template
  - options: enabled templates of this type
  - если нет enabled templates:
    - показать warning
    - кнопка “Перейти к шаблонам”

Кнопка:

- “Сохранить настройки”

После сохранения:

- показать success toast.

---

# 26. Поиск без Meilisearch

Поскольку Meilisearch запрещен, поиск реализовать на SQLite FTS5.

Логика:

1. Если FTS5 доступен:

```sql
SELECT snapshot_id
FROM snapshots_fts
WHERE snapshots_fts MATCH ?
ORDER BY rank
LIMIT ?
```

2. Если FTS5 недоступен:

использовать fallback:

```sql
SELECT snapshot_id
FROM snapshots
WHERE search_text LIKE ?
   OR title LIKE ?
   OR summary LIKE ?
LIMIT ?
```

3. Фильтры применять к основной таблице `snapshots`.

4. Sort:
   - для FTS: rank
   - для fallback: updated_at desc

5. Ответ должен включать:
   - snippet
   - matched terms
   - verified facts count

---

# 27. Обработка ошибок

Нужно всегда возвращать понятные ошибки.

Примеры:

- Директория не найдена:
  ```json
  {
    "error": "Directory not found",
    "detail": "Указанная директория не существует или недоступна"
  }
  ```

- Нет активного шаблона:
  ```json
  {
    "error": "No active template",
    "detail": "Для типа article нет активного шаблона. Создайте или включите шаблон на странице Шаблоны."
  }
  ```

- Модель недоступна:
  ```json
  {
    "error": "Provider unreachable",
    "detail": "Не удалось подключиться к Ollama на http://localhost:11434"
  }
  ```

- Модель не найдена:
  ```json
  {
    "error": "Model not found",
    "detail": "Модель llama3.1:8b не найдена в Ollama"
  }
  ```

- JSON не распознан:
  ```json
  {
    "error": "Invalid JSON",
    "detail": "Модель вернула невалидный JSON. Попробуйте другой шаблон или более сильную модель."
  }
  ```

---

# 28. UI/UX требования

Приложение должно быть:

- светлым;
- аккуратным;
- удобным;
- понятным;
- без лишнего визуального шума.

Дополнительные требования:

- все формы должны валидироваться;
- все ошибки должны показываться человекочитаемо;
- все длительные операции должны показывать прогресс;
- все JSON должны отображаться красиво;
- все бейджи должны быть единого стиля;
- мобильная версия должна работать;
- таблицы должны быть адаптивными;
- modals должны быть закрытыми;
- все кнопки должны иметь hover/active состояния.

---

# 29. Тестирование

Создать тесты:

## 29.1. JSON parser

Тесты:

- valid JSON
- JSON in markdown
- JSON with extra text
- invalid JSON
- empty response

## 29.2. Quote verification

Тесты:

- exact quote
- normalized whitespace
- quote not found
- quote partially matches
- multiple facts

## 29.3. Templates

Тесты:

- create template
- update template
- delete template
- invalid schema
- duplicate default for type
- template disabled

## 29.4. Search

Тесты:

- query match
- type filter
- provider filter
- min_confidence filter
- max_age_days filter
- empty query
- no results

## 29.5. Snapshot creation

Тесты:

- valid directory
- invalid directory
- no template
- model unavailable
- JSON parsing failure
- replace existing snapshot without creating version

---

# 30. Критерии готовности

Приложение считается готовым, если:

1. Можно выполнить:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

2. Открывается:
   ```bash
   http://127.0.0.1:8000
   ```

3. Все страницы работают:
   - Главная
   - Создание
   - Шаблоны
   - Поиск
   - Настройки
   - Детали слепа

4. Можно:
   - создать шаблон;
   - включить шаблон;
   - сделать его default;
   - проверить шаблон;
   - выбрать Ollama или LM Studio;
   - протестировать соединение;
   - указать директорию;
   - выбрать тип;
   - создать слепок;
   - увидеть прогресс;
   - получить успешный слепок;
   - найти его через поиск;
   - открыть детали;
   - скачать JSON;
   - удалить слепок.

5. При повторном создании для той же директории и типа:
   - старый слепок заменяется;
   - новая версия не сохраняется;
   - FTS обновляется.

6. Если модель возвращает невалидный JSON:
   - приложение не падает;
   - делает retry;
   - при неудаче показывает понятную ошибку.

7. Если цитата не найдена:
   - fact помечается как unverified;
   - confidence снижается;
   - пользователь видит это в UI.

8. UI:
   - светлый;
   - красивый;
   - адаптивный;
   - без JS-ошибок;
   - с понятными состояниями.

---

# 31. Финальное задание для AI

Теперь реализуй приложение полностью.

Ты должен:

1. Создать структуру проекта.
2. Написать `requirements.txt`.
3. Написать `README.md` с инструкцией запуска.
4. Реализовать FastAPI-приложение.
5. Реализовать SQLite-хранилище.
6. Реализовать FTS5-поиск.
7. Реализовать provider abstraction для Ollama и LM Studio.
8. Реализовать text extraction для md/txt/html/json/csv/yaml и опционально pdf.
9. Реализовать chunking и merge.
10. Реализовать robust JSON parser.
11. Реализовать quote verification.
12. Реализовать CRUD для templates.
13. Реализовать settings.
14. Реализовать jobs и progress.
15. Реализовать все страницы на Jinja2 + Tailwind CDN + Alpine.js.
16. Сделать светлый современный дизайн.
17. Добавить тесты.
18. Убедиться, что приложение запускается в venv.
23. Дать финальный список файлов и команды запуска.
