import importlib.util
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.models import Chunk, Course, Document
from app.schemas.settings import (
    ModelLoadRequest,
    ModelStatusResponse,
    PreflightCheck,
    PreflightResponse,
    StorageStatus,
    SystemStatusResponse,
)
from app.services.embedding_service import get_embedding_service
from app.services.llm_service import get_llm_service

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError):
        return False


def _directory_has_files(path: Path) -> bool:
    try:
        return path.is_dir() and any(path.iterdir())
    except OSError:
        return False


def _directory_is_writable(path: Path) -> bool:
    try:
        if not path.is_dir():
            return False
        with tempfile.NamedTemporaryFile(dir=path, prefix=".semestrack-check-"):
            return True
    except OSError:
        return False


def _get_models_status() -> ModelStatusResponse:
    llm_svc = get_llm_service()
    emb_svc = get_embedding_service()

    llm_info = llm_svc.get_status()
    emb_info = emb_svc.get_status()

    return ModelStatusResponse(
        llm_model_id=llm_info["llm_model_id"],
        llm_model_path=llm_info["llm_model_path"],
        llm_loaded=llm_info["llm_loaded"],
        llm_device=llm_info["llm_device"],
        lora_adapter_path=llm_info["lora_adapter_path"],
        lora_loaded=llm_info["lora_loaded"],
        embedding_model_id=emb_info["embedding_model_id"],
        embedding_model_path=emb_info["embedding_model_path"],
        embedding_loaded=emb_info["embedding_loaded"],
        embedding_device=emb_info["embedding_device"],
    )


@router.get("/preflight", response_model=PreflightResponse)
async def get_preflight(db: Session = Depends(get_db)) -> PreflightResponse:
    """Check local setup readiness without loading or downloading models."""
    database_ready = False
    fts_ready = False
    try:
        db.execute(text("SELECT 1"))
        database_ready = True
        db.execute(text("SELECT COUNT(*) FROM document_fts")).scalar_one()
        fts_ready = True
    except Exception:
        db.rollback()

    upload_writable = _directory_is_writable(settings.resolved_upload_dir)
    vector_storage_writable = _directory_is_writable(settings.resolved_chroma_dir)
    chroma_available = _module_available("chromadb")
    embedding_runtime_available = all(
        _module_available(name) for name in ("torch", "sentence_transformers")
    )
    llm_runtime_available = all(
        _module_available(name) for name in ("torch", "transformers")
    )
    embedding_files_available = _directory_has_files(settings.resolved_embedding_model_path)
    llm_files_available = _directory_has_files(settings.resolved_llm_model_path)
    vector_store_ready = False
    if chroma_available and vector_storage_writable:
        try:
            vector_store_ready = get_embedding_service().is_vector_store_ready()
        except Exception:
            vector_store_ready = False

    checks = [
        PreflightCheck(
            name="database",
            status="ready" if database_ready else "blocked",
            detail="Database connection is available."
            if database_ready
            else "Database is unavailable; check the configured database path and permissions.",
        ),
        PreflightCheck(
            name="fts5",
            status="ready" if fts_ready else "blocked",
            detail="SQLite FTS5 index is available."
            if fts_ready
            else "SQLite FTS5 index is unavailable; initialize or repair the database.",
        ),
        PreflightCheck(
            name="upload_storage",
            status="ready" if upload_writable else "blocked",
            detail="Upload storage is writable."
            if upload_writable
            else "Upload storage is missing or not writable.",
        ),
        PreflightCheck(
            name="chroma_package",
            status="ready" if chroma_available else "degraded",
            detail="ChromaDB is installed."
            if chroma_available
            else "ChromaDB is unavailable; semantic retrieval will be disabled.",
        ),
        PreflightCheck(
            name="vector_storage",
            status="ready" if vector_storage_writable else "degraded",
            detail="Vector storage is writable."
            if vector_storage_writable
            else "Vector storage is missing or not writable.",
        ),
        PreflightCheck(
            name="vector_store",
            status="ready" if vector_store_ready else "degraded",
            detail="Chroma vector collection is available."
            if vector_store_ready
            else "Chroma vector collection is unavailable; semantic retrieval will be disabled.",
        ),
        PreflightCheck(
            name="embedding_runtime",
            status="ready" if embedding_runtime_available else "degraded",
            detail="Embedding dependencies are installed."
            if embedding_runtime_available
            else "Install torch and sentence-transformers to enable embeddings.",
        ),
        PreflightCheck(
            name="embedding_model",
            status="ready" if embedding_files_available else "degraded",
            detail="Embedding model files are available locally."
            if embedding_files_available
            else "Embedding model files are missing; download them before offline use.",
        ),
        PreflightCheck(
            name="llm_runtime",
            status="ready" if llm_runtime_available else "degraded",
            detail="LLM dependencies are installed."
            if llm_runtime_available
            else "Install torch and transformers to enable local lesson generation.",
        ),
        PreflightCheck(
            name="llm_model",
            status="ready" if llm_files_available else "degraded",
            detail="LLM model files are available locally."
            if llm_files_available
            else "LLM model files are missing; download them before offline use.",
        ),
    ]

    core_ready = database_ready and fts_ready and upload_writable
    status_value = (
        "blocked"
        if not core_ready
        else "ready"
        if all(check.status == "ready" for check in checks)
        else "degraded"
    )
    return PreflightResponse(status=status_value, checks=checks)


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(db: Session = Depends(get_db)) -> SystemStatusResponse:
    """Retrieve full system health, offline model availability, and storage statistics."""
    # Check DB connectivity
    db_connected = False
    course_count = 0
    doc_count = 0
    chunk_count = 0
    try:
        db.execute(text("SELECT 1"))
        db_connected = True
        course_count = db.query(Course).count()
        doc_count = db.query(Document).count()
        chunk_count = db.query(Chunk).count()
    except Exception:
        db_connected = False

    upload_exists = settings.resolved_upload_dir.exists()
    chroma_exists = settings.resolved_chroma_dir.exists()

    storage_status = StorageStatus(
        database_connected=db_connected,
        database_url=settings.resolved_database_url,
        upload_dir=str(settings.resolved_upload_dir),
        upload_dir_exists=upload_exists,
        chroma_dir=str(settings.resolved_chroma_dir),
        chroma_dir_exists=chroma_exists,
        total_courses=course_count,
        total_documents=doc_count,
        total_chunks=chunk_count,
    )

    models_status = _get_models_status()
    overall_status = "ok" if db_connected else "degraded"

    return SystemStatusResponse(
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        status=overall_status,
        models=models_status,
        storage=storage_status,
        environment={
            "debug": settings.DEBUG,
            "log_level": settings.LOG_LEVEL,
            "host": settings.HOST,
            "port": settings.PORT,
            "ocr_enabled": settings.OCR_ENABLED,
        },
    )


@router.get("/models", response_model=ModelStatusResponse)
async def get_models_info() -> ModelStatusResponse:
    """Retrieve status of offline ML models (LLM and embedding)."""
    return _get_models_status()


@router.post("/models/load", response_model=ModelStatusResponse)
async def load_models(payload: ModelLoadRequest) -> ModelStatusResponse:
    """Explicitly trigger loading of offline models into memory."""
    if payload.load_embedding:
        emb_svc = get_embedding_service()
        emb_svc.load_model()

    if payload.load_llm:
        llm_svc = get_llm_service()
        llm_svc.load_model()

    if payload.load_lora and settings.resolved_lora_path:
        llm_svc = get_llm_service()
        llm_svc.load_lora_adapter(str(settings.resolved_lora_path))

    return _get_models_status()
