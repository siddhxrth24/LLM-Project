from typing import Any, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging_config import logger
from app.models.models import Chunk, Course, Document, Unit
from app.schemas.document import (
    ChunkResponse,
    DocumentResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
)
from app.services.document_service import (
    delete_document as svc_delete_document,
)
from app.services.document_service import (
    get_processing_status as svc_get_status,
)
from app.services.document_service import (
    process_document as svc_process_document,
)
from app.services.document_service import (
    save_upload,
)

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _to_document_response(doc: Document, db: Session, include_chunks: bool = False) -> DocumentResponse:
    chunk_count = db.query(Chunk).filter(Chunk.document_id == doc.id).count()

    chunks_list = None
    if include_chunks:
        db_chunks = (
            db.query(Chunk)
            .filter(Chunk.document_id == doc.id)
            .order_by(Chunk.chunk_index)
            .all()
        )
        chunks_list = [
            ChunkResponse(
                id=c.id,
                document_id=c.document_id,
                chunk_index=c.chunk_index,
                page_number=c.page_number,
                slide_number=c.slide_number,
                content=c.content,
                source_filename=c.source_filename,
            )
            for c in db_chunks
        ]

    return DocumentResponse(
        id=doc.id,
        unit_id=doc.unit_id,
        course_id=doc.course_id,
        filename=doc.filename,
        original_filename=doc.original_filename,
        file_type=doc.file_type,
        file_size=doc.file_size,
        status=doc.status,
        error_message=doc.error_message,
        page_count=doc.page_count,
        chunk_count=chunk_count,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        chunks=chunks_list,
    )


@router.post(
    "/upload/{course_id}/{unit_number}",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_documents(
    course_id: int,
    unit_number: int,
    files: list[UploadFile] = File(default=[]),
    file: Optional[UploadFile] = File(default=None),
    auto_process: bool = True,
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    """Upload one or more PDF/PPTX files to a specific unit of a course."""
    all_uploads: list[UploadFile] = []
    if file:
        all_uploads.append(file)
    if files:
        all_uploads.extend(files)

    if not all_uploads:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided in upload request",
        )

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {course_id} not found",
        )

    # Resolve or create unit
    unit = (
        db.query(Unit)
        .filter(Unit.course_id == course_id, Unit.unit_number == unit_number)
        .first()
    )
    if not unit:
        unit = Unit(
            course_id=course_id,
            unit_number=unit_number,
            name=f"Unit {unit_number}",
        )
        db.add(unit)
        db.commit()
        db.refresh(unit)

    saved_documents: list[DocumentResponse] = []
    for upload in all_uploads:
        doc = save_upload(
            file=upload,
            course_id=course_id,
            unit_id=unit.id,
            db=db,
        )
        if auto_process:
            try:
                svc_process_document(doc.id, db)
            except Exception as exc:
                logger.warning(f"Immediate processing failed for document {doc.id}: {exc}")

        db.refresh(doc)
        saved_documents.append(_to_document_response(doc, db))

    return DocumentUploadResponse(
        message=f"Successfully uploaded {len(saved_documents)} document(s)",
        documents=saved_documents,
    )


@router.get("/course/{course_id}", response_model=list[DocumentResponse])
async def list_course_documents(
    course_id: int,
    db: Session = Depends(get_db),
) -> list[DocumentResponse]:
    """List all documents uploaded to any unit within a course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {course_id} not found",
        )

    docs = (
        db.query(Document)
        .filter(Document.course_id == course_id)
        .order_by(Document.created_at.desc())
        .all()
    )
    return [_to_document_response(d, db) for d in docs]


@router.get("/unit/{course_id}/{unit_number}", response_model=list[DocumentResponse])
async def list_unit_documents(
    course_id: int,
    unit_number: int,
    db: Session = Depends(get_db),
) -> list[DocumentResponse]:
    """List all documents for a specific course unit."""
    unit = (
        db.query(Unit)
        .filter(Unit.course_id == course_id, Unit.unit_number == unit_number)
        .first()
    )
    if not unit:
        return []

    docs = (
        db.query(Document)
        .filter(Document.unit_id == unit.id)
        .order_by(Document.created_at.desc())
        .all()
    )
    return [_to_document_response(d, db) for d in docs]


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    include_chunks: bool = True,
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """Retrieve document details with optional chunks."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    return _to_document_response(doc, db, include_chunks=include_chunks)


@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
async def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Delete document, text chunks, vector embeddings, and physical file."""
    deleted = svc_delete_document(document_id, db)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    return {"message": "Document deleted successfully", "id": document_id}


@router.post("/{document_id}/process", response_model=DocumentResponse)
async def trigger_processing(
    document_id: int,
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """Manually trigger extraction, chunking, and indexing for a document."""
    doc = svc_process_document(document_id, db)
    return _to_document_response(doc, db)


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: int,
    db: Session = Depends(get_db),
) -> DocumentStatusResponse:
    """Get the current processing status and chunk statistics of a document."""
    status_info = svc_get_status(document_id, db)
    return DocumentStatusResponse(**status_info)
