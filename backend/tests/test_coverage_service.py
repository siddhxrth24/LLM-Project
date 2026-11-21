from app.models.models import Chunk, Document, SyllabusTopic, Unit
from app.services.syllabus_service import analyze_coverage


def _make_topic(db_session, test_course, subtopics: list[str]) -> tuple[SyllabusTopic, Unit]:
    unit = (
        db_session.query(Unit)
        .filter(Unit.course_id == test_course.id, Unit.unit_number == 1)
        .first()
    )
    topic = SyllabusTopic(
        course_id=test_course.id,
        unit_number=1,
        topic_name="Graph Theory",
        subtopics=subtopics,
        order_index=0,
    )
    db_session.add(topic)
    db_session.commit()
    db_session.refresh(topic)
    return topic, unit


def _add_uploaded_chunk(db_session, course_id: int, unit_id: int, text: str, suffix: str) -> Chunk:
    document = Document(
        unit_id=unit_id,
        course_id=course_id,
        filename=f"unit-{unit_id}-{suffix}.pdf",
        original_filename=f"unit-{unit_id}-{suffix}.pdf",
        file_type="pdf",
        file_size=100,
        file_path=f"unit-{unit_id}-{suffix}.pdf",
        status="completed",
    )
    db_session.add(document)
    db_session.flush()
    chunk = Chunk(
        document_id=document.id,
        course_id=course_id,
        unit_id=unit_id,
        content=text,
        chunk_index=0,
        page_number=2,
        slide_number=None,
        source_filename=document.filename,
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(chunk)
    return chunk


def test_coverage_scans_all_uploaded_chunks_and_uses_proportional_score(
    db_session,
    test_course,
) -> None:
    topic, unit = _make_topic(db_session, test_course, ["Vertices", "Edges", "Planar Graphs"])
    own_chunk = _add_uploaded_chunk(
        db_session,
        test_course.id,
        unit.id,
        "A graph-theory model contains vertices and edges.",
        "unit1",
    )
    # A matching term uploaded to another unit cannot increase this topic's score.
    other_unit = (
        db_session.query(Unit)
        .filter(Unit.course_id == test_course.id, Unit.unit_number == 2)
        .first()
    )
    _add_uploaded_chunk(db_session, test_course.id, other_unit.id, "Planar Graphs", "unit2")

    result = analyze_coverage(test_course.id, db_session)

    assert result.covered_count == 0
    assert result.partially_covered_count == 1
    assert result.coverage_percentage == 75.0
    analyzed = result.topics[0]
    assert analyzed.coverage_status == "partially_covered"
    assert analyzed.coverage_confidence == 0.75
    assert analyzed.coverage_evidence["matched_terms"] == ["Graph Theory", "Vertices", "Edges"]
    assert analyzed.coverage_evidence["citations"][0]["source_filename"] == own_chunk.source_filename


def test_coverage_matches_punctuation_variants_and_strips_syllabus_table_spill(
    db_session,
    test_course,
) -> None:
    topic, unit = _make_topic(
        db_session,
        test_course,
        ["Vertices", "Edges", "Policies Unit No. Unit Title U2 Dynamic Programming"],
    )
    _add_uploaded_chunk(
        db_session,
        test_course.id,
        unit.id,
        "Graph-Theory: vertices, edges, and policies.",
        "unit1",
    )

    result = analyze_coverage(test_course.id, db_session)

    assert result.covered_count == 1
    assert result.coverage_percentage == 100.0
    assert result.topics[0].coverage_evidence["total_terms"] == 4
    assert result.topics[0].coverage_evidence["matched_terms"] == [
        "Graph Theory",
        "Vertices",
        "Edges",
        "Policies",
    ]


def test_coverage_without_matching_terms_needs_review_not_covered(
    db_session,
    test_course,
) -> None:
    topic, unit = _make_topic(db_session, test_course, ["Vertices", "Edges"])
    _add_uploaded_chunk(db_session, test_course.id, unit.id, "Unrelated material about topology.", "unit1")

    result = analyze_coverage(test_course.id, db_session)

    assert result.needs_review_count == 1
    assert result.coverage_percentage == 0.0
    assert result.topics[0].coverage_evidence["citations"] == []
