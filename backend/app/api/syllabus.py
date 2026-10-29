from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Course, SyllabusTopic
from app.schemas.syllabus import (
    CoverageAnalysisResponse,
    SyllabusTopicResponse,
    SyllabusTopicUpdate,
)
from app.services.syllabus_service import (
    analyze_coverage,
    get_coverage_summary,
)

router = APIRouter(prefix="/api/syllabus", tags=["syllabus"])


def _to_topic_response(topic: SyllabusTopic) -> SyllabusTopicResponse:
    effective = (
        topic.user_override_status
        if topic.user_override_status
        else topic.coverage_status
    )
    return SyllabusTopicResponse(
        id=topic.id,
        course_id=topic.course_id,
        unit_number=topic.unit_number,
        topic_name=topic.topic_name,
        subtopics=topic.subtopics or [],
        order_index=topic.order_index,
        prerequisites=topic.prerequisites or [],
        estimated_hours=topic.estimated_hours,
        difficulty=topic.difficulty,
        coverage_status=topic.coverage_status,
        coverage_confidence=topic.coverage_confidence,
        coverage_evidence=topic.coverage_evidence or {},
        user_override_status=topic.user_override_status,
        effective_status=effective,
        created_at=topic.created_at,
        updated_at=topic.updated_at,
    )


@router.get("/topics/{course_id}", response_model=list[SyllabusTopicResponse])
async def get_course_topics(
    course_id: int,
    db: Session = Depends(get_db),
) -> list[SyllabusTopicResponse]:
    """Retrieve all syllabus topics defined for a course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {course_id} not found",
        )

    topics = (
        db.query(SyllabusTopic)
        .filter(SyllabusTopic.course_id == course_id)
        .order_by(SyllabusTopic.unit_number, SyllabusTopic.order_index)
        .all()
    )
    return [_to_topic_response(t) for t in topics]


@router.post("/analyze/{course_id}", response_model=CoverageAnalysisResponse)
async def run_coverage_analysis(
    course_id: int,
    db: Session = Depends(get_db),
) -> CoverageAnalysisResponse:
    """Run RAG-based coverage analysis across uploaded documents for all topics in a course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {course_id} not found",
        )

    return analyze_coverage(course_id, db)


@router.put("/topics/{topic_id}", response_model=SyllabusTopicResponse)
async def update_topic(
    topic_id: int,
    payload: SyllabusTopicUpdate,
    db: Session = Depends(get_db),
) -> SyllabusTopicResponse:
    """Update topic properties or apply manual coverage status override."""
    topic = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id).first()
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Syllabus topic {topic_id} not found",
        )

    update_dict = payload.model_dump(exclude_unset=True)
    for field, val in update_dict.items():
        setattr(topic, field, val)

    db.commit()
    db.refresh(topic)
    return _to_topic_response(topic)


@router.get("/coverage/{course_id}", response_model=CoverageAnalysisResponse)
async def get_coverage(
    course_id: int,
    db: Session = Depends(get_db),
) -> CoverageAnalysisResponse:
    """Get summarized coverage status metrics for a course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {course_id} not found",
        )

    return get_coverage_summary(course_id, db)
