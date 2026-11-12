from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from . import config


class SettingsOut(BaseModel):
    provider: str = "ollama"
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    language: str = "en"
    temperature: float = 0.1
    top_p: float = 0.9
    seed: int = 42
    max_tokens: int = 2000
    timeout_seconds: int = 0
    json_mode: bool = True
    max_input_chars: int = 12000
    max_chunk_chars: int = 6000
    server_url: str = ""
    default_templates: dict[str, Optional[int]] = Field(default_factory=dict)


class SettingsUpdate(BaseModel):
    provider: str = "ollama"
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    language: str = "en"
    temperature: float = 0.1
    top_p: float = 0.9
    seed: int = 42
    max_tokens: int = 2000
    timeout_seconds: int = 0
    json_mode: bool = True
    max_input_chars: int = 12000
    max_chunk_chars: int = 6000
    server_url: str = ""
    default_templates: dict[str, Optional[int]] = Field(default_factory=dict)


class ProviderTestIn(BaseModel):
    provider: str = "ollama"
    base_url: str = ""
    api_key: str = ""
    model: str = ""


class ProviderTestOut(BaseModel):
    reachable: bool = False
    model_available: bool = False
    models: list[str] = Field(default_factory=list)
    error: Optional[str] = None


class ServerTestIn(BaseModel):
    server_url: str = ""


class ServerTestOut(BaseModel):
    reachable: bool = False
    status_code: Optional[int] = None
    error: Optional[str] = None


class TemplateIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str = ""
    snapshot_type: str = "general"
    system_prompt: str = ""
    user_prompt: str = ""
    chunk_user_prompt: str = ""
    merge_user_prompt: str = ""
    template_schema: str = Field(default="{}", alias="schema_json")
    enabled: bool = True
    is_default: bool = False


class TemplateOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    name: str
    description: str = ""
    snapshot_type: str
    system_prompt: str = ""
    user_prompt: str = ""
    chunk_user_prompt: str = ""
    merge_user_prompt: str = ""
    template_schema: str = Field(default="{}", alias="schema_json")
    enabled: bool = True
    is_default: bool = False
    created_at: str = ""
    updated_at: str = ""


class TemplateTestIn(BaseModel):
    sample_text: str = ""
    directory: str = "/tmp/test"
    type: str = "general"


class TemplateTestOut(BaseModel):
    success: bool = False
    raw_output: str = ""
    parsed_json: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class SnapshotCreate(BaseModel):
    directory: str
    snapshot_type: str = "general"
    max_files: int = 200
    max_chars: Optional[int] = None
    source_url: str = ""


class SnapshotFromUrl(BaseModel):
    url: str
    snapshot_type: str = "webpage"
    max_chars: Optional[int] = None


class SourceUrlUpdate(BaseModel):
    source_url: str = ""


class JobOut(BaseModel):
    id: int
    snapshot_type: str
    directory_path: str
    template_id: Optional[int] = None
    status: str = "pending"
    progress: int = 0
    step: str = "queued"
    step_label: str = ""
    error: Optional[str] = None
    snapshot_id: Optional[str] = None
    created_at: str = ""
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class SnapshotListItem(BaseModel):
    snapshot_id: str
    title: Optional[str] = None
    directory: str
    source_url: str = ""
    type: str
    summary: Optional[str] = None
    confidence: float = 0.0
    provider: str = ""
    model: str = ""
    template_name: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    updated_at: str = ""
    snippet: str = ""
    verified_facts: int = 0
    total_facts: int = 0


class SnapshotListOut(BaseModel):
    total: int = 0
    limit: int = 20
    offset: int = 0
    items: list[SnapshotListItem] = Field(default_factory=list)


class HybridSearchHealth(BaseModel):
    available: bool = False
    model: str = ""


class HealthOut(BaseModel):
    status: str = "ok"
    provider: str = ""
    model: str = ""
    provider_reachable: bool = False
    model_available: bool = False
    snapshot_count: int = 0
    template_count: int = 0
    # гибридный поиск (ChromaDB + BM25)
    ollama: HybridSearchHealth = Field(default_factory=HybridSearchHealth)
    vector_index_size: int = 0
    chroma_available: bool = False
