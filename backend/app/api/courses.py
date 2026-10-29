import shutil
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.logging_config import logger
from app.models.models import Chunk, Course, Document, SyllabusTopic, Unit
from app.schemas.course import (
    CourseCreate,
    CourseListResponse,
    CourseResponse,
    CourseUpdate,
    UnitSummary,
)
from app.schemas.syllabus import SyllabusParseRequest, SyllabusTopicResponse
from app.services.syllabus_service import parse_syllabus

router = APIRouter(prefix="/api/courses", tags=["courses"])


def _build_course_response(course: Course, db: Session) -> CourseResponse:
    """Helper to assemble a comprehensive CourseResponse with relationship metrics."""
    unit_records = (
        db.query(Unit)
        .filter(Unit.course_id == course.id)
        .order_by(Unit.unit_number)
        .all()
    )

    doc_count = db.query(Document).filter(Document.course_id == course.id).count()
    topic_count = (
        db.query(SyllabusTopic).filter(SyllabusTopic.course_id == course.id).count()
    )

    unit_summaries: list[UnitSummary] = []
    for u in unit_records:
        u_docs = db.query(Document).filter(Document.unit_id == u.id).count()
        unit_summaries.append(
            UnitSummary(
                id=u.id,
                unit_number=u.unit_number,
                name=u.name,
                document_count=u_docs,
            )
        )

    return CourseResponse(
        id=course.id,
        name=course.name,
        syllabus_text=course.syllabus_text,
        exam_date=course.exam_date,
        study_days_per_week=course.study_days_per_week,
        daily_study_hours=course.daily_study_hours,
        difficulty_preference=course.difficulty_preference,
        created_at=course.created_at,
        updated_at=course.updated_at,
        unit_count=len(unit_records),
        document_count=doc_count,
        topic_count=topic_count,
        units=unit_summaries,
    )


@router.post("/", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(payload: CourseCreate, db: Session = Depends(get_db)) -> CourseResponse:
    """Create a new course and instantiate default 5 units."""
    course = Course(
        name=payload.name,
        syllabus_text=payload.syllabus_text,
        exam_date=payload.exam_date,
        study_days_per_week=payload.study_days_per_week,
        daily_study_hours=payload.daily_study_hours,
        difficulty_preference=payload.difficulty_preference,
    )
    db.add(course)
    db.commit()
    db.refresh(course)

    # Automatically generate 5 standard academic units for the course
    for u_num in range(1, 6):
        unit = Unit(
            course_id=course.id,
            unit_number=u_num,
            name=f"Unit {u_num}",
        )
        db.add(unit)
    db.commit()

    # If initial syllabus text was supplied, parse topics immediately
    if payload.syllabus_text and len(payload.syllabus_text.strip()) > 10:
        try:
            parse_syllabus(payload.syllabus_text, course.id, db)
        except Exception as exc:
            logger.warning(f"Initial syllabus auto-parsing failed: {exc}")

    db.refresh(course)
    return _build_course_response(course, db)


@router.get("/", response_model=CourseListResponse)
async def list_courses(db: Session = Depends(get_db)) -> CourseListResponse:
    """List all registered courses with unit, document, and topic counts."""
    courses = db.query(Course).order_by(Course.created_at.desc()).all()
    results = [_build_course_response(c, db) for c in courses]
    return CourseListResponse(courses=results, total=len(results))


@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(course_id: int, db: Session = Depends(get_db)) -> CourseResponse:
    """Retrieve detailed course information."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {course_id} not found",
        )
    return _build_course_response(course, db)


@router.put("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: int,
    payload: CourseUpdate,
    db: Session = Depends(get_db),
) -> CourseResponse:
    """Update course attributes."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {course_id} not found",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(course, key, value)

    db.commit()
    db.refresh(course)
    return _build_course_response(course, db)


@router.delete("/{course_id}", status_code=status.HTTP_200_OK)
async def delete_course(course_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Delete course and associated disk storage."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {course_id} not found",
        )

    # Clean course files on disk
    course_dir = settings.resolved_upload_dir / f"course_{course_id}"
    if course_dir.exists():
        try:
            shutil.rmtree(course_dir)
        except Exception as exc:
            logger.warning(f"Failed to delete course directory {course_dir}: {exc}")

    db.delete(course)
    db.commit()
    return {"message": "Course deleted successfully", "id": course_id}


@router.post("/{course_id}/syllabus", response_model=list[SyllabusTopicResponse])
async def upload_syllabus(
    course_id: int,
    payload: SyllabusParseRequest,
    db: Session = Depends(get_db),
) -> list[SyllabusTopicResponse]:
    """Upload or update syllabus text and trigger topic extraction."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {course_id} not found",
        )

    topics = parse_syllabus(payload.syllabus_text, course_id, db)

    response_list: list[SyllabusTopicResponse] = []
    for t in topics:
        effective = t.user_override_status if t.user_override_status else t.coverage_status
        response_list.append(
            SyllabusTopicResponse(
                id=t.id,
                course_id=t.course_id,
                unit_number=t.unit_number,
                topic_name=t.topic_name,
                subtopics=t.subtopics or [],
                order_index=t.order_index,
                prerequisites=t.prerequisites or [],
                estimated_hours=t.estimated_hours,
                difficulty=t.difficulty,
                coverage_status=t.coverage_status,
                coverage_confidence=t.coverage_confidence,
                coverage_evidence=t.coverage_evidence or {},
                user_override_status=t.user_override_status,
                effective_status=effective,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
        )

    return response_list
