from app.models.models import Chunk, Course, Unit
from app.services.keyword_service import index_chunks_batch
from app.services.retrieval_service import format_context, hybrid_search


def test_keyword_fallback_preserves_slide_citations(
    db_session,
    test_course: Course,
    monkeypatch,
) -> None:
    import app.services.retrieval_service as retrieval_service

    unit = db_session.query(Unit).filter_by(course_id=test_course.id, unit_number=1).one()
    chunk = Chunk(
        document_id=1,
        course_id=test_course.id,
        unit_id=unit.id,
        content="Topological ordering follows a directed acyclic graph.",
        chunk_index=0,
        slide_number=7,
        source_filename="graphs.pptx",
    )
    db_session.add(chunk)
    db_session.flush()
    index_chunks_batch(
        db_session,
        [
            {
                "id": chunk.id,
                "course_id": test_course.id,
                "unit_id": unit.id,
                "slide_number": chunk.slide_number,
                "source_filename": chunk.source_filename,
                "content": chunk.content,
            }
        ],
    )

    class NoDenseResults:
        def search_dense(self, **_) -> list[dict]:
            return []

    monkeypatch.setattr(retrieval_service, "get_embedding_service", lambda: NoDenseResults())

    results = hybrid_search(
        db_session,
        query="topological ordering",
        course_id=test_course.id,
        unit_id=unit.id,
    )

    assert len(results) == 1
    assert results[0]["page_number"] is None
    assert results[0]["slide_number"] == 7
    assert "Slide 7" in format_context(results)
    assert "Page 7" not in format_context(results)