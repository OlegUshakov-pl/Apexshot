from __future__ import annotations

from urllib.parse import urlparse

from . import config, i18n

JOB_STATUSES = ["pending", "processing", "success", "failed", "cancelled"]

FACT_TYPES = ["verified", "inferred", "opinion"]

FACT_QUALITY = ["ok", "low_quality"]

LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def normalize_directory(path: str) -> str:
    raw = (path or "").strip().strip('"')
    p = raw.replace("\\", "/")
    while "//" in p:
        p = p.replace("//", "/")
    if len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    if len(p) > 2 and p[1] == ":":
        p = p[0].lower() + p[1:]
    return p or raw.strip()


def snapshot_type_label(value: str) -> str:
    return i18n.t(config.TYPE_LABELS.get(value, value))


def source_url_host(url: str) -> str:
    try:
        host = (urlparse((url or "").strip()).hostname or "")
    except ValueError:
        return ""
    return host.lower()


def is_valid_source_url(url: str) -> bool:
    try:
        parts = urlparse((url or "").strip())
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.hostname)


def is_local_url(url: str) -> bool:
    host = source_url_host(url)
    if not host:
        return False
    if host in LOCAL_HOSTS:
        return True
    if host.startswith("127.") or host.endswith(".localhost"):
        return True
    return False


def normalize_source_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    try:
        parts = urlparse(raw)
    except ValueError:
        return raw
    if not parts.scheme or not parts.hostname:
        return raw
    host = parts.hostname.lower()
    netloc = host
    if parts.port:
        netloc = f"{host}:{parts.port}"
    rebuilt = f"{parts.scheme.lower()}://{netloc}{parts.path or ''}"
    if parts.query:
        rebuilt += f"?{parts.query}"
    return rebuilt.rstrip("/") or rebuilt


def step_label(value: str) -> str:
    return i18n.t(config.STEP_LABELS.get(value, value))
