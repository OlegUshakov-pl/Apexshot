from __future__ import annotations

from . import config, i18n

JOB_STATUSES = ["pending", "processing", "success", "failed", "cancelled"]

FACT_TYPES = ["verified", "inferred", "opinion"]

FACT_QUALITY = ["ok", "low_quality"]


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


def step_label(value: str) -> str:
    return i18n.t(config.STEP_LABELS.get(value, value))
