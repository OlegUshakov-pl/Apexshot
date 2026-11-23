from __future__ import annotations

BASE_SYSTEM_PROMPT = """You create an AI snapshot — a small machine-readable JSON file.

Return a single valid JSON object only.
Do not return markdown, explanations, comments, or any text outside the JSON.

Rules:
1. Use only the provided text.
2. Do not add outside knowledge.
3. Do not invent facts.
4. Every fact must contain a quote field — an exact quote from the source text.
5. If information is missing, use empty lists or null.
6. summary must be short and neutral.
7. confidence — from 0.0 to 1.0.
8. If the text is promotional, incomplete, or noisy, lower confidence.
9. search_text — a search string built from title, summary, tags, topics, technologies, and key claims.
10. The response must fit within the token limit. Keep within the volume limits:
    no more than 8 facts, 4 sections, 6 highlights, 10 tags, 8 questions;
    claim — up to 150 characters, quote — up to 300 characters, summary — up to 600 characters,
    section text — up to 400 characters. Write nothing extra.
11. Always write every field of the snapshot (title, summary, sections, claims, questions,
    tags, entities, search_text, reasons) in English, no matter what language the source
    text is in. The only exception: quote fields must stay verbatim in the source language,
    because they are verified against the original text."""

DEFAULT_USER_PROMPT = """Create an AI snapshot.

Type: {type}
Directory: {directory}
Files: {files}

Source text:
{text}

Return strict JSON matching the schema:
{schema}"""

DEFAULT_CHUNK_PROMPT = """Summarize only this text fragment.

Type: {type}
Directory: {directory}
Fragment {chunk_index} of {chunk_count}

Text:
{text}

Return JSON:
{schema}"""

DEFAULT_MERGE_PROMPT = """Partial snapshots are given:

{partials}

Merge them into one final AI snapshot.

Rules:
1. Use only the provided partial data.
2. Remove duplicate facts.
3. Keep only important and verifiable facts.
4. Every quote must exist in the source text.
5. Return the final JSON matching the schema:
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
    "article": "Template for articles and long-form posts",
    "documentation": "Template for technical documentation",
    "news": "Template for news articles",
    "forum": "Template for discussions and forum threads",
    "notes": "Template for personal notes",
    "general": "Universal template for any directory",
    "software": "Template for application projects: README, stack, run instructions, features, screenshots",
    "site": "Template for websites: pages, navigation, design, stack, screenshots",
    "webpage": "Template for a snapshot of a web page by URL: content, structure, links",
}

SOFTWARE_SYSTEM_PROMPT = BASE_SYSTEM_PROMPT + """

Additional rules for a Software Snapshot:
1. Priority — README.md / README.rst / docs: purpose, features, installation, running, configs.
2. Detect the stack: language(s), framework (Django, FastAPI, Flask, Streamlit, NiceGUI, Next.js, React, Vue, etc.), database, queues, Docker. Only write what is explicitly visible in the text (requirements.txt, pyproject.toml, package.json, Dockerfile, imports). Do not guess.
3. technologies: languages, frameworks, libraries, databases, build/deploy tools.
4. In sections, include up to 4 of: Overview / Stack / Installation and running / Structure and configs / Screenshots and media.
5. The list of images/media files is provided separately — describe them by name (which screenshot it is, which section it belongs to); do not invent their content.
6. facts: requirements, run commands, environment variables, versions — each with an exact quote."""

SITE_SYSTEM_PROMPT = BASE_SYSTEM_PROMPT + """

Additional rules for a Site Snapshot:
1. Priority — README.md, index.html, page texts, navigation, meta tags.
2. Detect the site stack: generator/CMS (Next.js, React, Vue, Nuxt, Hugo, Jekyll, WordPress, etc.), CSS (Tailwind, Bootstrap), hosting/deploy — only from explicit signs in the text. Do not guess.
3. technologies: frameworks, CMS, CSS, JS libraries, hosting.
4. In sections, include up to 4 of: Overview / Pages and navigation / Design and content / Stack / Screenshots and media.
5. The list of images/media files is provided separately — match them to site sections by name/path (hero, landing, screenshots); do not invent image content.
6. facts: pages, routes, contacts, links, deploy instructions — each with an exact quote."""

SOFTWARE_USER_PROMPT = """Create a Software Snapshot of the project.

Type: {type}
Directory: {directory}
Files: {files}
Media files (images, describe them by name, do not invent content): {media_files}

Pay special attention to: README.md (purpose, features, installation/running), dependency manifests
(requirements.txt, pyproject.toml, package.json, go.mod, Dockerfile, docker-compose.yml),
source code (imports of Django / FastAPI / Flask / Streamlit / NiceGUI / Next.js, etc.).

Source text:
{text}

Return strict JSON matching the schema:
{schema}"""

SITE_USER_PROMPT = """Create a Site Snapshot of the website.

Type: {type}
Directory: {directory}
Files: {files}
Media files (images, match them to pages by name, do not invent content): {media_files}

Pay special attention to: README.md, HTML (title, meta, h1, nav, footer, links), page texts,
framework configs (package.json, next.config.*, astro.config.*, _config.yml), stack signs
(Next.js, React, Vue, Nuxt, Hugo, Jekyll, WordPress, Tailwind, Bootstrap, etc.).

Source text:
{text}

Return strict JSON matching the schema:
{schema}"""

WEBPAGE_SYSTEM_PROMPT = BASE_SYSTEM_PROMPT + """

Additional rules for a Webpage Snapshot:
1. The source is a single web page: describe its content, structure, and purpose.
2. technologies: only what is explicitly visible in the text (frameworks, CMS, analytics).
3. In sections, include up to 4 of: Overview / Content / Structure and navigation / Links and contacts.
4. facts: headings, key claims, links, contacts — each with an exact quote."""

WEBPAGE_USER_PROMPT = """Create a Webpage Snapshot of the page.

Type: {type}
Page URL: {directory}
Files: {files}

Page source text:
{text}

Return strict JSON matching the schema:
{schema}"""

_TYPE_PROMPTS = {
    "software": (SOFTWARE_SYSTEM_PROMPT, SOFTWARE_USER_PROMPT),
    "site": (SITE_SYSTEM_PROMPT, SITE_USER_PROMPT),
    "webpage": (WEBPAGE_SYSTEM_PROMPT, WEBPAGE_USER_PROMPT),
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
        "webpage",
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
