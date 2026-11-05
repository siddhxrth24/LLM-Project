import shutil
import uuid
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
from app.services.syllabus_service import (
    SyllabusLLMUnavailableError,
    parse_syllabus,
)
from app.services.embedding_service import get_embedding_service
from app.services.keyword_service import delete_course_chunks as delete_course_fts

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
    db.flush()

    for unit_number in range(1, 6):
        db.add(
            Unit(
                course_id=course.id,
                unit_number=unit_number,
                name=f"Unit {unit_number}",
            )
        )

    if payload.syllabus_text and payload.syllabus_text.strip():
        try:
            parse_syllabus(payload.syllabus_text.strip(), course.id, db)
        except SyllabusLLMUnavailableError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        except ValueError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

    db.commit()
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
    syllabus_was_updated = "syllabus_text" in update_data
    new_syllabus = update_data.pop("syllabus_text", None)
    for key, value in update_data.items():
        setattr(course, key, value)

    if syllabus_was_updated:
        cleaned_syllabus = new_syllabus.strip() if new_syllabus else ""
        if cleaned_syllabus:
            try:
                parse_syllabus(cleaned_syllabus, course.id, db)
            except SyllabusLLMUnavailableError as exc:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=str(exc),
                ) from exc
            except ValueError as exc:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(exc),
                ) from exc
        else:
            db.query(SyllabusTopic).filter(
                SyllabusTopic.course_id == course.id
            ).delete(synchronize_session=False)
            course.syllabus_text = None

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

    try:
        vectors_deleted = get_embedding_service().delete_course_chunks(course_id)
    except Exception as exc:
        logger.error(f"Failed deleting vectors for course {course_id}: {exc}")
        vectors_deleted = False
    if not vectors_deleted:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector cleanup failed; the course was not deleted.",
        )

    course_dir = settings.resolved_upload_dir / f"course_{course_id}"
    quarantined_dir = course_dir.with_name(
        f".{course_dir.name}.{uuid.uuid4().hex}.deleting"
    )
    try:
        if course_dir.exists():
            course_dir.replace(quarantined_dir)

        delete_course_fts(db, course_id)
        db.delete(course)
        db.commit()
    except Exception as exc:
        db.rollback()
        if quarantined_dir.exists():
            try:
                quarantined_dir.replace(course_dir)
            except OSError as restore_exc:
                logger.error(
                    f"Failed to restore course directory {course_dir}: {restore_exc}"
                )
        logger.error(f"Failed to delete course {course_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Course cleanup failed; the database record was retained.",
        ) from exc

    if quarantined_dir.exists():
        try:
            shutil.rmtree(quarantined_dir)
        except OSError as exc:
            logger.warning(f"Could not remove quarantined course directory: {exc}")
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

    try:
        topics = parse_syllabus(payload.syllabus_text, course_id, db)
        db.commit()
    except SyllabusLLMUnavailableError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception:
        db.rollback()
        raise

    for topic in topics:
        db.refresh(topic)

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
