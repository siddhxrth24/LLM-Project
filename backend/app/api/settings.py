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
    StorageStatus,
    SystemStatusResponse,
)
from app.services.embedding_service import get_embedding_service
from app.services.llm_service import get_llm_service

router = APIRouter(prefix="/api/settings", tags=["settings"])


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
