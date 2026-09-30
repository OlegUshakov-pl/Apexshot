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
9. search_text — строка для поиска, состоящая из title, summary, tags, topics, technologies и ключевых claims."""

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
    ]:
        templates.append(
            {
                "name": f"{type_key.capitalize()} Snapshot",
                "description": TEMPLATE_DESCRIPTIONS[type_key],
                "snapshot_type": type_key,
                "system_prompt": BASE_SYSTEM_PROMPT,
                "user_prompt": DEFAULT_USER_PROMPT,
                "chunk_user_prompt": DEFAULT_CHUNK_PROMPT,
                "merge_user_prompt": DEFAULT_MERGE_PROMPT,
                "schema_json": schema_json,
                "enabled": 1,
                "is_default": 1,
            }
        )
    return templates
