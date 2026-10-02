from __future__ import annotations

BASE_SYSTEM_PROMPT = """Ты создаешь AI-слепок — маленький машиночитаемый JSON-файл.

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
10. Ответ должен помещаться в лимит токенов. Соблюдай ограничения объёма:
    не больше 8 facts, 4 sections, 6 highlights, 10 tags, 8 questions;
    claim — до 150 символов, quote — до 300 символов, summary — до 600 символов,
    текст секции — до 400 символов. Не пиши ничего лишнего."""

DEFAULT_USER_PROMPT = """Сформируй AI-слепок.

Тип: {type}
Директория: {directory}
Файлы: {files}

Исходный текст:
{text}

Верни строго JSON по схеме:
{schema}"""

DEFAULT_CHUNK_PROMPT = """Суммаризируй только этот фрагмент текста.

Тип: {type}
Директория: {directory}
Фрагмент {chunk_index} из {chunk_count}

Текст:
{text}

Верни JSON:
{schema}"""

DEFAULT_MERGE_PROMPT = """Даны частичные слепки:

{partials}

Объедини их в один финальный AI-слепок.

Правила:
1. Используй только предоставленные частичные данные.
2. Удали дублирующиеся факты.
3. Сохрани только важные и проверяемые факты.
4. Каждая цитата должна существовать в исходном тексте.
5. Верни финальный JSON по схеме:
{schema}"""

SNAPSHOT_SCHEMA = {
    "type": "object",
    "required": [
        "title",
        "summary",
        "facts",
        "highlights",
        "entities",
        "questions",
        "tags",
        "confidence",
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
                    "text": {"type": "string"},
                },
            },
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
                        "enum": ["verified", "inferred", "opinion"],
                    },
                },
            },
        },
        "highlights": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["quote"],
                "properties": {
                    "quote": {"type": "string"},
                    "file": {"type": "string"},
                    "reason": {"type": "string"},
                },
            },
        },
        "entities": {
            "type": "object",
            "required": [
                "topics",
                "organizations",
                "people",
                "technologies",
                "locations",
                "dates",
            ],
            "properties": {
                "topics": {"type": "array", "items": {"type": "string"}},
                "organizations": {"type": "array", "items": {"type": "string"}},
                "people": {"type": "array", "items": {"type": "string"}},
                "technologies": {"type": "array", "items": {"type": "string"}},
                "locations": {"type": "array", "items": {"type": "string"}},
                "dates": {"type": "array", "items": {"type": "string"}},
            },
        },
        "questions": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
        "search_text": {"type": "string"},
    },
}

TEMPLATE_DESCRIPTIONS = {
    "article": "Шаблон для статей и лонгридов",
    "documentation": "Шаблон для технической документации",
    "news": "Шаблон для новостных материалов",
    "forum": "Шаблон для обсуждений и форумных веток",
    "notes": "Шаблон для личных заметок",
    "general": "Универсальный шаблон для любых директорий",
    "software": "Шаблон для проектов приложений: README, стек, запуск, фичи, скриншоты",
    "site": "Шаблон для сайтов: страницы, навигация, дизайн, стек, скриншоты",
}

SOFTWARE_SYSTEM_PROMPT = BASE_SYSTEM_PROMPT + """

Дополнительно для Software Snapshot:
1. Приоритет — README.md / README.rst / docs: назначение, фичи, установка, запуск, конфиги.
2. Определи стек: язык(и), фреймворк (Django, FastAPI, Flask, Streamlit, NiceGUI, Next.js, React, Vue и т.п.), БД, очереди, Docker. Пиши только то, что явно видно в тексте (requirements.txt, pyproject.toml, package.json, Dockerfile, импорты). Не угадывай.
3. technologies: языки, фреймворки, библиотеки, БД, инструменты сборки/деплоя.
4. В sections сделай до 4 из: Обзор / Стек / Установка и запуск / Структура и конфиги / Скриншоты и медиа.
5. Список images/медиафайлов дан отдельно — опиши их по именам (что за скриншот, к какому разделу относится), не выдумывай содержимое.
6. facts: требования, команды запуска, переменные окружения, версии — каждый с точной quote."""

SITE_SYSTEM_PROMPT = BASE_SYSTEM_PROMPT + """

Дополнительно для Site Snapshot:
1. Приоритет — README.md, index.html, тексты страниц, навигация, мета-теги.
2. Определи стек сайта: генератор/CMS (Next.js, React, Vue, Nuxt, Hugo, Jekyll, WordPress и т.п.), CSS (Tailwind, Bootstrap), хостинг/деплой — только по явным признакам в тексте. Не угадывай.
3. technologies: фреймворки, CMS, CSS, JS-библиотеки, хостинг.
4. В sections сделай до 4 из: Обзор / Страницы и навигация / Дизайн и контент / Стек / Скриншоты и медиа.
5. Список images/медиафайлов дан отдельно — сопоставь с разделами сайта по именам/путям (hero, landing, screenshots), не выдумывай содержимое картинок.
6. facts: страницы, роуты, контакты, ссылки, инструкции деплоя — каждый с точной quote."""

SOFTWARE_USER_PROMPT = """Сформируй Software Snapshot проекта.

Тип: {type}
Директория: {directory}
Файлы: {files}
Медиафайлы (images, опиши по именам, содержимое не выдумывай): {media_files}

Особое внимание: README.md (назначение, фичи, установка/запуск), манифесты зависимостей
(requirements.txt, pyproject.toml, package.json, go.mod, Dockerfile, docker-compose.yml),
исходники (импорты Django / FastAPI / Flask / Streamlit / NiceGUI / Next.js и т.п.).

Исходный текст:
{text}

Верни строго JSON по схеме:
{schema}"""

SITE_USER_PROMPT = """Сформируй Site Snapshot сайта.

Тип: {type}
Директория: {directory}
Файлы: {files}
Медиафайлы (images, сопоставь со страницами по именам, содержимое не выдумывай): {media_files}

Особое внимание: README.md, HTML (title, meta, h1, nav, footer, ссылки), тексты страниц,
конфиги фреймворков (package.json, next.config.*, astro.config.*, _config.yml), признаки
стека (Next.js, React, Vue, Nuxt, Hugo, Jekyll, WordPress, Tailwind, Bootstrap и т.п.).

Исходный текст:
{text}

Верни строго JSON по схеме:
{schema}"""

_TYPE_PROMPTS = {
    "software": (SOFTWARE_SYSTEM_PROMPT, SOFTWARE_USER_PROMPT),
    "site": (SITE_SYSTEM_PROMPT, SITE_USER_PROMPT),
}


def build_default_templates() -> list[dict]:
    import json

    schema_json = json.dumps(SNAPSHOT_SCHEMA, ensure_ascii=False, indent=2)
    templates = []
    for type_key in [
        "article",
        "documentation",
        "news",
        "forum",
        "notes",
        "general",
        "software",
        "site",
    ]:
        system_prompt, user_prompt = _TYPE_PROMPTS.get(
            type_key, (BASE_SYSTEM_PROMPT, DEFAULT_USER_PROMPT)
        )
        templates.append(
            {
                "name": f"{type_key.capitalize()} Snapshot",
                "description": TEMPLATE_DESCRIPTIONS[type_key],
                "snapshot_type": type_key,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "chunk_user_prompt": DEFAULT_CHUNK_PROMPT,
                "merge_user_prompt": DEFAULT_MERGE_PROMPT,
                "schema_json": schema_json,
                "enabled": 1,
                "is_default": 1,
            }
        )
    return templates
