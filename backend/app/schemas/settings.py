from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ModelStatusResponse(BaseModel):
    """Status details for offline ML models."""

    llm_model_id: str
    llm_model_path: str
    llm_loaded: bool
    llm_device: str
    lora_adapter_path: Optional[str] = None
    lora_loaded: bool = False
    embedding_model_id: str
    embedding_model_path: str
    embedding_loaded: bool
    embedding_device: str


class StorageStatus(BaseModel):
    """Status details for databases and file directories."""

    database_connected: bool
    database_url: str
    upload_dir: str
    upload_dir_exists: bool
    chroma_dir: str
    chroma_dir_exists: bool
    total_courses: int = 0
    total_documents: int = 0
    total_chunks: int = 0


class SystemStatusResponse(BaseModel):
    """High-level system health and configuration status."""

    app_name: str
    version: str
    status: str = Field(default="ok", description="'ok' or 'degraded'")
    models: ModelStatusResponse
    storage: StorageStatus
    environment: dict[str, Any] = Field(default_factory=dict)


class PreflightCheck(BaseModel):
    name: str
    status: Literal["ready", "degraded", "blocked"]
    detail: str


class PreflightResponse(BaseModel):
    status: Literal["ready", "degraded", "blocked"]
    checks: list[PreflightCheck]


class ModelLoadRequest(BaseModel):
    """Request to trigger model loading."""

    load_llm: bool = Field(default=True, description="Load LLM causal model")
    load_embedding: bool = Field(default=True, description="Load sentence embedding model")
    load_lora: bool = Field(default=False, description="Load LoRA adapter if configured")
