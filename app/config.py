from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("SHOT_DATA_DIR", BASE_DIR / "data"))
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
DB_PATH = DATA_DIR / "snapshots.db"

SNAPSHOT_TYPES = ["article", "documentation", "news", "forum", "notes", "general"]

PROVIDERS = ["ollama", "lmstudio", "anthropic", "openai", "google", "mistral", "groq", "deepseek", "openrouter", "opencode"]

PROVIDER_TYPES = {
    "ollama": "local",
    "lmstudio": "local",
    "openrouter": "aggregator",
    "anthropic": "cloud",
    "openai": "cloud",
    "google": "cloud",
    "mistral": "cloud",
    "groq": "cloud",
    "deepseek": "cloud",
    "opencode": "cloud",
}

PROVIDER_NAMES = {
    "ollama": "Ollama",
    "lmstudio": "LM Studio",
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "google": "Google AI",
    "mistral": "Mistral",
    "groq": "Groq",
    "deepseek": "DeepSeek",
    "openrouter": "OpenRouter",
    "opencode": "OpenCode",
}

KEY_URLS = {
    "anthropic": "https://console.anthropic.com/settings/keys",
    "openai": "https://platform.openai.com/api-keys",
    "google": "https://aistudio.google.com/app/apikey",
    "mistral": "https://console.mistral.ai/api-keys",
    "groq": "https://console.groq.com/keys",
    "deepseek": "https://platform.deepseek.com/api_keys",
    "openrouter": "https://openrouter.ai/keys",
    "opencode": "https://opencode.ai/settings/keys",
}

DEFAULT_BASE_URLS = {
    "ollama": "http://localhost:11434",
    "lmstudio": "http://localhost:1234/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "openai": "https://api.openai.com/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta",
    "mistral": "https://api.mistral.ai/v1",
    "groq": "https://api.groq.com/openai/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "opencode": "https://opencode.ai/zen/v1",
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
    "language": "en",
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
