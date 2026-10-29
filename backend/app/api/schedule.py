from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Course, StudySession, SyllabusTopic
from app.schemas.schedule import (
    ScheduleGenerateRequest,
    ScheduleResponse,
    StudySessionResponse,
    StudySessionUpdate,
)
from app.services.schedule_service import (
    generate_schedule,
    recalculate_schedule,
)

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


def _format_session(session: StudySession, topic: Optional[SyllabusTopic]) -> StudySessionResponse:
    return StudySessionResponse(
        id=session.id,
        course_id=session.course_id,
        topic_id=session.topic_id,
        topic_name=topic.topic_name if topic else None,
        unit_number=topic.unit_number if topic else None,
        scheduled_date=session.scheduled_date,
        duration_hours=session.duration_hours,
        session_type=session.session_type,
        is_completed=session.is_completed,
        completed_at=session.completed_at,
        notes=session.notes,
        order_index=session.order_index,
    )


@router.post("/generate/{course_id}", response_model=ScheduleResponse)
async def create_schedule(
    course_id: int,
    payload: Optional[ScheduleGenerateRequest] = None,
    db: Session = Depends(get_db),
) -> ScheduleResponse:
    """Generate a structured, topologically sorted study and revision timeline."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {course_id} not found",
        )

    start_date = payload.start_date if payload else None
    study_days = payload.study_days_per_week if payload else None
    daily_hours = payload.daily_study_hours if payload else None
    rev_ratio = payload.revision_ratio if payload else 0.2

    return generate_schedule(
        course_id=course_id,
        db=db,
        start_date=start_date,
        study_days_per_week=study_days,
        daily_study_hours=daily_hours,
        revision_ratio=rev_ratio,
    )


@router.get("/{course_id}", response_model=ScheduleResponse)
async def get_schedule(
    course_id: int,
    db: Session = Depends(get_db),
) -> ScheduleResponse:
    """Retrieve existing schedule for a course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {course_id} not found",
        )

    sessions = (
        db.query(StudySession)
        .filter(StudySession.course_id == course_id)
        .order_by(StudySession.order_index, StudySession.scheduled_date)
        .all()
    )

    topics = (
        db.query(SyllabusTopic).filter(SyllabusTopic.course_id == course_id).all()
    )
    topic_map = {t.id: t for t in topics}

    session_responses = [_format_session(s, topic_map.get(s.topic_id)) for s in sessions]
    total_hours = sum(s.duration_hours for s in sessions)
    start_date = sessions[0].scheduled_date if sessions else None

    return ScheduleResponse(
        course_id=course_id,
        total_sessions=len(sessions),
        total_hours=round(total_hours, 1),
        start_date=start_date,
        exam_date=course.exam_date,
        is_feasible=True,
        conflicts=[],
        sessions=session_responses,
    )


@router.put("/session/{session_id}", response_model=StudySessionResponse)
async def update_session(
    session_id: int,
    payload: StudySessionUpdate,
    db: Session = Depends(get_db),
) -> StudySessionResponse:
    """Update progress, notes, or date for an individual study session."""
    session = db.query(StudySession).filter(StudySession.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"StudySession {session_id} not found",
        )

    if payload.is_completed is not None:
        session.is_completed = payload.is_completed
        if payload.is_completed and not session.completed_at:
            session.completed_at = datetime.utcnow()
        elif not payload.is_completed:
            session.completed_at = None

    if payload.notes is not None:
        session.notes = payload.notes
    if payload.scheduled_date is not None:
        session.scheduled_date = payload.scheduled_date
    if payload.duration_hours is not None:
        session.duration_hours = payload.duration_hours

    db.commit()
    db.refresh(session)

    topic = None
    if session.topic_id:
        topic = (
            db.query(SyllabusTopic)
            .filter(SyllabusTopic.id == session.topic_id)
            .first()
        )

    return _format_session(session, topic)


@router.post("/recalculate/{course_id}", response_model=ScheduleResponse)
async def recalculate(
    course_id: int,
    db: Session = Depends(get_db),
) -> ScheduleResponse:
    """Dynamically recalculate timetable for incomplete topics starting from today."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {course_id} not found",
        )

    return recalculate_schedule(course_id, db)
