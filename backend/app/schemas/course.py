from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UnitSummary(BaseModel):
    """Summary of a unit within a course."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Unique unit identifier")
    unit_number: int = Field(..., ge=1, le=10, description="Unit index (typically 1-5)")
    name: str = Field(..., description="Unit title/name")
    document_count: int = Field(default=0, description="Number of uploaded documents in this unit")


class CourseBase(BaseModel):
    """Common attributes for a course."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Course title",
        examples=["Database Management Systems"],
    )
    syllabus_text: Optional[str] = Field(
        default=None,
        description="Raw syllabus text for topic parsing",
        examples=["Unit 1: Relational Model\nUnit 2: SQL and Normalization"],
    )
    exam_date: Optional[date] = Field(
        default=None,
        description="Target final exam date (YYYY-MM-DD)",
        examples=["2026-12-15"],
    )
    study_days_per_week: int = Field(
        default=5,
        ge=1,
        le=7,
        description="Number of available study days per week (1-7)",
        examples=[5],
    )
    daily_study_hours: float = Field(
        default=2.0,
        gt=0.0,
        le=24.0,
        description="Target study hours per available day",
        examples=[2.0],
    )
    difficulty_preference: str = Field(
        default="balanced",
        description="Study pacing preference: easy, balanced, or challenging",
        examples=["balanced"],
    )

    @field_validator("difficulty_preference")
    @classmethod
    def validate_difficulty_preference(cls, v: str) -> str:
        allowed = {"easy", "balanced", "challenging"}
        cleaned = v.strip().lower()
        if cleaned not in allowed:
            raise ValueError(f"difficulty_preference must be one of {allowed}")
        return cleaned


class CourseCreate(CourseBase):
    """Schema for creating a new course."""
    pass


class CourseUpdate(BaseModel):
    """Schema for updating an existing course."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    syllabus_text: Optional[str] = None
    exam_date: Optional[date] = None
    study_days_per_week: Optional[int] = Field(None, ge=1, le=7)
    daily_study_hours: Optional[float] = Field(None, gt=0.0, le=24.0)
    difficulty_preference: Optional[str] = None

    @field_validator("difficulty_preference")
    @classmethod
    def validate_difficulty_preference(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        allowed = {"easy", "balanced", "challenging"}
        cleaned = v.strip().lower()
        if cleaned not in allowed:
            raise ValueError(f"difficulty_preference must be one of {allowed}")
        return cleaned


class CourseResponse(CourseBase):
    """Schema returned for a course detail."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Course ID")
    created_at: datetime
    updated_at: datetime
    unit_count: int = Field(default=0, description="Total units associated with the course")
    document_count: int = Field(default=0, description="Total documents uploaded for this course")
    topic_count: int = Field(default=0, description="Total syllabus topics extracted")
    units: list[UnitSummary] = Field(default_factory=list, description="Units in this course")


class CourseListResponse(BaseModel):
    """Response containing a list of courses."""

    courses: list[CourseResponse]
    total: int
