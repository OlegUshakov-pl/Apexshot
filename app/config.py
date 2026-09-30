from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("SHOT_DATA_DIR", BASE_DIR / "data"))
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
DB_PATH = DATA_DIR / "snapshots.db"

SNAPSHOT_TYPES = ["article", "documentation", "news", "forum", "notes", "general"]

PROVIDERS = ["ollama", "lmstudio"]

DEFAULT_BASE_URLS = {
    "ollama": "http://localhost:11434",
    "lmstudio": "http://localhost:1234/v1",
}

TEXT_EXTENSIONS = {
    ".md",
    ".markdown",
    ".txt",
    ".rst",
    ".csv",
    ".json",
    ".yaml",
    ".yml",
    ".html",
    ".htm",
    ".xml",
    ".log",
    ".py",
    ".toml",
    ".ini",
    ".cfg",
}

PDF_EXTENSION = ".pdf"

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    ".cache",
    ".idea",
    ".vscode",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    "site-packages",
    "data",
}

SKIP_FILES = {".DS_Store", "Thumbs.db"}

MAX_FILE_BYTES = 10 * 1024 * 1024

DEFAULTS = {
    "provider": "ollama",
    "base_url": DEFAULT_BASE_URLS["ollama"],
    "api_key": "",
    "model": "",
    "temperature": 0.1,
    "top_p": 0.9,
    "seed": 42,
    "max_tokens": 2000,
    "timeout_seconds": 300,
    "json_mode": 1,
    "max_input_chars": 12000,
    "max_chunk_chars": 6000,
    "default_templates_json": "{}",
}

STEP_LABELS = {
    "queued": "Очередь",
    "checking_directory": "Проверка директории",
    "collecting_files": "Сбор файлов",
    "extracting_text": "Очистка текста",
    "generating": "Генерация",
    "parsing_json": "Проверка JSON",
    "verifying_quotes": "Проверка цитат",
    "saving": "Сохранение",
    "done": "Готово",
}

TYPE_LABELS = {
    "article": "Статья",
    "documentation": "Документация",
    "news": "Новости",
    "forum": "Форум",
    "notes": "Заметки",
    "general": "Общий",
}
