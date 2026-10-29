from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ScheduleGenerateRequest(BaseModel):
    """Parameters to generate or recalculate study schedule."""

    start_date: Optional[date] = Field(
        default=None,
        description="Schedule start date (defaults to today if omitted)",
        examples=["2026-11-01"],
    )
    study_days_per_week: Optional[int] = Field(
        default=None,
        ge=1,
        le=7,
        description="Override course study days per week",
    )
    daily_study_hours: Optional[float] = Field(
        default=None,
        gt=0.0,
        le=24.0,
        description="Override daily study hours",
    )
    revision_ratio: float = Field(
        default=0.2,
        ge=0.0,
        le=0.5,
        description="Proportion of total time allocated for revision sessions (0.0 to 0.5)",
    )


class StudySessionUpdate(BaseModel):
    """Schema for updating a single study session."""

    is_completed: Optional[bool] = Field(None, description="Mark session as completed")
    notes: Optional[str] = Field(None, description="Student notes for this session")
    scheduled_date: Optional[date] = Field(None, description="Rescheduled date")
    duration_hours: Optional[float] = Field(None, gt=0.0, le=24.0)


class StudySessionResponse(BaseModel):
    """Response representing a single scheduled study session."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    topic_id: Optional[int] = None
    topic_name: Optional[str] = Field(None, description="Topic name if linked")
    unit_number: Optional[int] = Field(None, description="Unit number if linked")
    scheduled_date: date
    duration_hours: float
    session_type: str = Field(..., description="'study' or 'revision'")
    is_completed: bool
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None
    order_index: int


class ScheduleResponse(BaseModel):
    """Complete study schedule for a course."""

    course_id: int
    total_sessions: int
    total_hours: float
    start_date: Optional[date]
    exam_date: Optional[date]
    is_feasible: bool = Field(
        ...,
        description="True if all topics fit before the exam date without exceeding daily hours",
    )
    conflicts: list[str] = Field(
        default_factory=list,
        description="Constraint conflicts or cycle warnings detected during schedule planning",
    )
    sessions: list[StudySessionResponse] = Field(default_factory=list)
