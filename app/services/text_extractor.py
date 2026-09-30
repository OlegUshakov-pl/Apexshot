from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .. import config

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    BeautifulSoup = None  # type: ignore[assignment]

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None  # type: ignore[assignment]


@dataclass
class Document:
    file: str
    title: str
    text: str


_HTML_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def collect_files(directory: str, max_files: int = 200) -> list[Path]:
    root = Path(directory)
    results: list[Path] = []
    skip_ext = {config.PDF_EXTENSION} if PdfReader is None else set()
    for path in sorted(root.rglob("*")):
        if len(results) >= max_files:
            break
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts
        if any(part in config.SKIP_DIRS or part.startswith(".") for part in rel_parts[:-1]):
            continue
        if path.name in config.SKIP_FILES or path.name.startswith("."):
            continue
        ext = path.suffix.lower()
        if ext in skip_ext:
            continue
        if ext not in config.TEXT_EXTENSIONS and ext != config.PDF_EXTENSION:
            continue
        try:
            if path.stat().st_size > config.MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        results.append(path)
    return results


def read_text(path: Path) -> Optional[str]:
    ext = path.suffix.lower()
    if ext == config.PDF_EXTENSION:
        return _read_pdf(path)
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw[:8192]:
        return None
    for encoding in ("utf-8", "utf-8-sig", "cp1251"):
        try:
            text = raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
        return text
    return None


def _read_pdf(path: Path) -> Optional[str]:
    if PdfReader is None:
        return None
    try:
        reader = PdfReader(str(path))
        parts = []
        for page in reader.pages[:100]:
            parts.append(page.extract_text() or "")
        return "\n".join(parts)
    except Exception:
        return None


def extract_documents(directory: str, max_files: int = 200) -> list[Document]:
    root = Path(directory)
    docs: list[Document] = []
    for path in collect_files(directory, max_files):
        text = read_text(path)
        if text is None:
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        ext = path.suffix.lower()
        title = ""
        if ext in (".html", ".htm"):
            title, text = extract_html(text)
        elif ext == ".json":
            text = _pretty_json(text)
        if not title:
            title = _first_heading(text) or path.stem
        text = normalize_text(text)
        if not text.strip():
            continue
        docs.append(Document(file=rel, title=title or path.stem, text=text))
    return docs


def extract_html(html: str) -> tuple[str, str]:
    if BeautifulSoup is None:
        return "", _HTML_TAGS.sub(" ", html)
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "aside", "form", "noscript", "svg"]):
        tag.decompose()
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    node = (
        soup.select_one("article main")
        or soup.select_one("main")
        or soup.select_one("article")
        or soup.body
        or soup
    )
    text = node.get_text("\n") if hasattr(node, "get_text") else str(node)
    return title, text


def _first_heading(text: str) -> str:
    for line in text.splitlines()[:20]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
        if stripped.startswith("=") or stripped.startswith("-"):
            continue
        return stripped[:120]
    return ""


def _pretty_json(text: str) -> str:
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return text
    return json.dumps(data, ensure_ascii=False, indent=2)


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    text = _WS.sub(" ", text)
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = _BLANK_LINES.sub("\n\n", text)
    return text.strip()


def build_corpus(docs: list[Document]) -> str:
    parts = []
    for doc in docs:
        parts.append(f"### Файл: {doc.file}\nЗаголовок: {doc.title}\n\n{doc.text}")
    return "\n\n".join(parts)
