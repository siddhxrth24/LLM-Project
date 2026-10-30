import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging_config import logger
from app.models.models import Chunk, Document
from app.services.embedding_service import get_embedding_service
from app.services.extraction_service import (
    chunk_text,
    extract_pdf,
    extract_pptx,
    sanitize_filename,
)
from app.services.keyword_service import delete_chunks as fts_delete_chunks
from app.services.keyword_service import index_chunks_batch

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {"pdf", "pptx"}


def validate_file(file: UploadFile) -> tuple[bool, str, str]:
    """
    Validate uploaded file extension and content type.

    Returns:
        (is_valid, error_message, file_type)
    """
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Unsupported file type '.{ext}'. Allowed types are: {', '.join(ALLOWED_EXTENSIONS)}", ""

    return True, "", ext


def save_upload(
    file: UploadFile,
    course_id: int,
    unit_id: int,
    db: Session,
) -> Document:
    """
    Save an uploaded file safely to disk and create a pending Document record in DB.
    """
    is_valid, err, file_type = validate_file(file)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)

    original_name = file.filename or "upload"
    safe_base = sanitize_filename(original_name)
    stem = Path(safe_base).stem
    suffix = Path(safe_base).suffix

    # Create destination directory: UPLOAD_DIR / course_{id} / unit_{id}
    target_dir = settings.resolved_upload_dir / f"course_{course_id}" / f"unit_{unit_id}"
    target_dir.mkdir(parents=True, exist_ok=True)

    # Guarantee unique filename
    unique_filename = f"{stem}_{uuid.uuid4().hex[:8]}{suffix}"
    dest_path = target_dir / unique_filename

    # Read and write content with size check
    bytes_written = 0
    try:
        with open(dest_path, "wb") as out_file:
            while chunk := file.file.read(1024 * 1024):  # 1MB chunks
                bytes_written += len(chunk)
                if bytes_written > MAX_FILE_SIZE_BYTES:
                    # Clean up and abort
                    out_file.close()
                    if dest_path.exists():
                        dest_path.unlink()
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024*1024)} MB",
                    )
                out_file.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        if dest_path.exists():
            dest_path.unlink()
        logger.error(f"Failed to save upload {original_name}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write file to storage: {exc}",
        )

    # Create database record
    doc = Document(
        course_id=course_id,
        unit_id=unit_id,
        filename=unique_filename,
        original_filename=original_name,
        file_type=file_type,
        file_size=bytes_written,
        file_path=str(dest_path),
        status="pending",
        page_count=0,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    logger.info(f"Saved document {doc.id} ({doc.original_filename}) to {dest_path}")
    return doc


def process_document(document_id: int, db: Session) -> Document:
    """
    Process an uploaded document:
    1. Extract pages / slides text
    2. Segment into chunks
    3. Save chunks in DB
    4. Index chunks in SQLite FTS5
    5. Compute and store embeddings in ChromaDB
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )

    doc.status = "processing"
    doc.error_message = None
    db.commit()

    file_path = Path(doc.file_path)
    if not file_path.exists():
        doc.status = "failed"
        doc.error_message = f"File missing from disk: {doc.file_path}"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=doc.error_message,
        )

    try:
        # 1. Extraction
        if doc.file_type.lower() == "pdf":
            pages = extract_pdf(file_path)
        elif doc.file_type.lower() == "pptx":
            pages = extract_pptx(file_path)
        else:
            raise ValueError(f"Unsupported file type: {doc.file_type}")

        doc.page_count = len(pages)

        # 2. Chunking
        raw_chunks = chunk_text(
            pages=pages,
            chunk_size=400,
            overlap=80,
            source_type=doc.file_type,
            source_filename=doc.original_filename,
        )

        # 3. Clear old indexes before replacing the relational chunks.
        fts_delete_chunks(db, doc.id)
        embedding_svc = get_embedding_service()
        if not embedding_svc.delete_chunks(doc.id):
            raise RuntimeError("Could not remove existing vector entries before reprocessing.")

        db.query(Chunk).filter(Chunk.document_id == doc.id).delete()

        db_chunks: list[Chunk] = []
        for rc in raw_chunks:
            chunk_record = Chunk(
                document_id=doc.id,
                course_id=doc.course_id,
                unit_id=doc.unit_id,
                content=rc["content"],
                chunk_index=rc["chunk_index"],
                page_number=rc.get("page_number"),
                slide_number=rc.get("slide_number"),
                source_filename=rc["source_filename"],
                metadata_json=rc.get("metadata", {}),
            )
            db.add(chunk_record)
            db_chunks.append(chunk_record)

        db.flush()

        # 4. FTS5 full-text indexing
        chunks_payload: list[dict[str, Any]] = [
            {
                "id": c.id,
                "course_id": doc.course_id,
                "unit_id": doc.unit_id,
                "source_filename": c.source_filename,
                "page_number": c.page_number,
                "slide_number": c.slide_number,
                "content": c.content,
            }
            for c in db_chunks
        ]
        if chunks_payload:
            index_chunks_batch(db, chunks_payload)
        else:
            db.commit()

        # 5. Chroma vector embeddings
        try:
            chroma_ids = embedding_svc.store_chunks(
                chunks=[{"content": c.content, "chunk_index": c.chunk_index, "id": c.id, "source_filename": c.source_filename, "page_number": c.page_number, "slide_number": c.slide_number} for c in db_chunks],
                course_id=doc.course_id,
                unit_id=doc.unit_id,
                document_id=doc.id,
            )
            for c, cid in zip(db_chunks, chroma_ids):
                c.embedding_id = cid
            db.commit()
        except Exception as emb_exc:
            logger.warning(
                f"Embedding creation deferred/failed for document {doc.id}: {emb_exc}"
            )

        doc.status = "completed"
        doc.error_message = None
        db.commit()
        db.refresh(doc)
        logger.info(
            f"Successfully processed document {doc.id} ({len(db_chunks)} chunks)"
        )
        return doc

    except Exception as exc:
        db.rollback()
        logger.error(f"Failed processing document {doc.id}: {exc}")
        doc.status = "failed"
        doc.error_message = str(exc)
        db.commit()
        db.refresh(doc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document processing failed: {exc}",
        )


def delete_document(document_id: int, db: Session) -> bool:
    """
    Remove document record, corresponding chunks, FTS entries, Chroma vectors, and physical file.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        return False

    # Vector storage is independent of the SQL transaction; abort if cleanup fails.
    try:
        vectors_deleted = get_embedding_service().delete_chunks(document_id)
    except Exception as exc:
        logger.error(f"Failed deleting Chroma vectors for document {document_id}: {exc}")
        vectors_deleted = False
    if not vectors_deleted:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector cleanup failed; the document was not deleted.",
        )

    file_path = Path(doc.file_path)
    quarantined_path: Path | None = None
    try:
        if file_path.exists():
            quarantined_path = file_path.with_name(
                f".{file_path.name}.{uuid.uuid4().hex}.deleting"
            )
            file_path.replace(quarantined_path)

        fts_delete_chunks(db, document_id)
        db.delete(doc)
        db.commit()
    except Exception as exc:
        db.rollback()
        if quarantined_path and quarantined_path.exists():
            try:
                quarantined_path.replace(file_path)
            except OSError as restore_exc:
                logger.error(
                    f"Failed to restore document file {file_path} after cleanup error: "
                    f"{restore_exc}"
                )
        if isinstance(exc, HTTPException):
            raise
        logger.error(f"Failed to delete document {document_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document cleanup failed; the database record was retained.",
        ) from exc

    if quarantined_path:
        try:
            quarantined_path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning(f"Could not remove quarantined file {quarantined_path}: {exc}")

    logger.info(f"Deleted document {document_id}")
    return True


def get_processing_status(document_id: int, db: Session) -> dict[str, Any]:
    """Retrieve document processing status and chunk statistics."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )

    chunk_count = db.query(Chunk).filter(Chunk.document_id == document_id).count()
    return {
        "id": doc.id,
        "status": doc.status,
        "error_message": doc.error_message,
        "page_count": doc.page_count,
        "chunk_count": chunk_count,
    }
