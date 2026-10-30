from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.models.models import Chunk, Course, Document, Unit
from app.core.database import migrate_schema
from app.services.keyword_service import index_chunks_batch


class FakeEmbeddingService:
    def __init__(self, *, delete_succeeds: bool = True) -> None:
        self.delete_succeeds = delete_succeeds
        self.deleted_documents: list[int] = []

    def delete_chunks(self, document_id: int) -> bool:
        self.deleted_documents.append(document_id)
        return self.delete_succeeds

    def store_chunks(
        self,
        chunks: list[dict],
        course_id: int,
        unit_id: int,
        document_id: int,
    ) -> list[str]:
        return [f"vector-{document_id}-{chunk['chunk_index']}" for chunk in chunks]


def create_document(
    db: Session,
    course: Course,
    unit: Unit,
    file_path: Path,
    content: str,
) -> tuple[Document, Chunk]:
    file_path.write_bytes(b"test upload")
    document = Document(
        course_id=course.id,
        unit_id=unit.id,
        filename=file_path.name,
        original_filename=file_path.name,
        file_type="pdf",
        file_size=file_path.stat().st_size,
        file_path=str(file_path),
        status="completed",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    chunk = Chunk(
        document_id=document.id,
        course_id=course.id,
        unit_id=unit.id,
        content=content,
        chunk_index=0,
        page_number=1,
        source_filename=document.original_filename,
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    index_chunks_batch(
        db,
        [
            {
                "id": chunk.id,
                "course_id": course.id,
                "unit_id": unit.id,
                "source_filename": chunk.source_filename,
                "page_number": chunk.page_number,
                "content": chunk.content,
            }
        ],
    )
    return document, chunk


def test_reprocessing_replaces_fts_chunks_and_cleans_orphans(
    db_session: Session,
    test_course: Course,
    tmp_path,
    monkeypatch,
) -> None:
    import app.services.document_service as document_service

    unit = db_session.query(Unit).filter_by(course_id=test_course.id, unit_number=1).one()
    document, old_chunk = create_document(
        db_session, test_course, unit, tmp_path / "lecture.pdf", "stale lecture terminology"
    )
    db_session.execute(
        text(
            "INSERT INTO document_fts "
            "(chunk_id, course_id, unit_id, source_filename, page_number, content) "
            "VALUES ('orphan', '1', '1', 'old.pdf', '1', 'orphan search result')"
        )
    )
    db_session.commit()

    vectors = FakeEmbeddingService()
    monkeypatch.setattr(document_service, "get_embedding_service", lambda: vectors)
    monkeypatch.setattr(document_service, "extract_pdf", lambda _: [(1, "replacement text")])
    monkeypatch.setattr(
        document_service,
        "chunk_text",
        lambda **_: [
            {
                "content": "replacement lecture material",
                "chunk_index": 0,
                "page_number": 1,
                "source_filename": document.original_filename,
                "metadata": {},
            }
        ],
    )

    result = document_service.process_document(document.id, db_session)

    chunks = db_session.query(Chunk).filter_by(document_id=document.id).all()
    indexed_content = db_session.execute(
        text("SELECT content FROM document_fts ORDER BY rowid")
    ).scalars().all()
    assert result.status == "completed"
    assert len(chunks) == 1
    assert chunks[0].content == "replacement lecture material"
    assert chunks[0].embedding_id == f"vector-{document.id}-0"
    assert indexed_content == ["replacement lecture material"]
    assert vectors.deleted_documents == [document.id]
    assert old_chunk.id != chunks[0].id or old_chunk.content != chunks[0].content


def test_delete_cleans_file_sql_fts_and_vector_state(
    db_session: Session,
    test_course: Course,
    tmp_path,
    monkeypatch,
) -> None:
    import app.services.document_service as document_service

    unit = db_session.query(Unit).filter_by(course_id=test_course.id, unit_number=1).one()
    document, _ = create_document(
        db_session, test_course, unit, tmp_path / "remove.pdf", "remove this material"
    )
    vectors = FakeEmbeddingService()
    monkeypatch.setattr(document_service, "get_embedding_service", lambda: vectors)

    assert document_service.delete_document(document.id, db_session) is True

    assert db_session.get(Document, document.id) is None
    assert db_session.query(Chunk).filter_by(document_id=document.id).count() == 0
    assert db_session.execute(text("SELECT COUNT(*) FROM document_fts")).scalar_one() == 0
    assert not Path(document.file_path).exists()
    assert vectors.deleted_documents == [document.id]


def test_delete_aborts_without_vector_cleanup(
    db_session: Session,
    test_course: Course,
    tmp_path,
    monkeypatch,
) -> None:
    import app.services.document_service as document_service

    unit = db_session.query(Unit).filter_by(course_id=test_course.id, unit_number=1).one()
    document, _ = create_document(
        db_session, test_course, unit, tmp_path / "keep.pdf", "keep this material"
    )
    vectors = FakeEmbeddingService(delete_succeeds=False)
    monkeypatch.setattr(document_service, "get_embedding_service", lambda: vectors)

    with pytest.raises(HTTPException) as error:
        document_service.delete_document(document.id, db_session)

    assert error.value.status_code == 503
    assert db_session.get(Document, document.id) is not None
    assert db_session.query(Chunk).filter_by(document_id=document.id).count() == 1
    assert db_session.execute(text("SELECT COUNT(*) FROM document_fts")).scalar_one() == 1
    assert Path(document.file_path).exists()


def test_delete_restores_file_when_fts_cleanup_fails(
    tmp_path,
    monkeypatch,
) -> None:
    import app.services.document_service as document_service

    engine = create_engine(f"sqlite:///{tmp_path / 'rollback.db'}")
    migrate_schema(engine)
    try:
        with Session(engine, expire_on_commit=False) as db_session:
            course = Course(name="Rollback Course")
            db_session.add(course)
            db_session.commit()
            db_session.refresh(course)
            unit = Unit(course_id=course.id, unit_number=1, name="Unit 1")
            db_session.add(unit)
            db_session.commit()
            db_session.refresh(unit)

            document, _ = create_document(
                db_session, course, unit, tmp_path / "restore.pdf", "restore this material"
            )
            document_id = document.id
            original_path = Path(document.file_path)
            vectors = FakeEmbeddingService()
            monkeypatch.setattr(document_service, "get_embedding_service", lambda: vectors)

            def fail_fts_cleanup(*_) -> None:
                raise RuntimeError("FTS is unavailable")

            monkeypatch.setattr(document_service, "fts_delete_chunks", fail_fts_cleanup)

            with pytest.raises(HTTPException) as error:
                document_service.delete_document(document_id, db_session)

            assert error.value.status_code == 500
            assert db_session.get(Document, document_id) is not None
            assert db_session.query(Chunk).filter_by(document_id=document_id).count() == 1
            assert db_session.execute(text("SELECT COUNT(*) FROM document_fts")).scalar_one() == 1
            assert original_path.exists()
            assert list(tmp_path.glob("*.deleting")) == []
    finally:
        engine.dispose()