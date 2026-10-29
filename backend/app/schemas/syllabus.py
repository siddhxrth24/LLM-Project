from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SyllabusParseRequest(BaseModel):
    """Request payload to parse raw syllabus text."""

    syllabus_text: str = Field(
        ...,
        min_length=10,
        description="Raw syllabus text containing units and topic listings",
        examples=[
            "Unit 1: Introduction to Operating Systems, Process Management\n"
            "Unit 2: Memory Management, Virtual Memory, Paging"
        ],
    )


class SyllabusTopicCreate(BaseModel):
    """Schema for manually creating a syllabus topic."""

    unit_number: int = Field(..., ge=1, le=10, description="Unit index (1-5)")
    topic_name: str = Field(..., min_length=1, max_length=255, description="Topic title")
    subtopics: list[str] = Field(default_factory=list, description="Subtopic bullet points")
    order_index: int = Field(default=0, ge=0, description="Sequencing order")
    prerequisites: list[Any] = Field(
        default_factory=list, description="List of prerequisite topic IDs or names"
    )
    estimated_hours: float = Field(
        default=2.0, gt=0.0, le=50.0, description="Estimated study hours"
    )
    difficulty: int = Field(
        default=3, ge=1, le=5, description="Difficulty level from 1 (easy) to 5 (hard)"
    )


class SyllabusTopicUpdate(BaseModel):
    """Schema for updating topic fields and user coverage override."""

    topic_name: Optional[str] = Field(None, min_length=1, max_length=255)
    subtopics: Optional[list[str]] = None
    order_index: Optional[int] = Field(None, ge=0)
    prerequisites: Optional[list[Any]] = None
    estimated_hours: Optional[float] = Field(None, gt=0.0, le=50.0)
    difficulty: Optional[int] = Field(None, ge=1, le=5)
    coverage_status: Optional[str] = None
    user_override_status: Optional[str] = Field(
        None,
        description="User override status: covered, partially_covered, not_found, or needs_review",
    )

    @field_validator("coverage_status", "user_override_status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        allowed = {"covered", "partially_covered", "not_found", "needs_review"}
        cleaned = v.strip().lower()
        if cleaned not in allowed:
            raise ValueError(f"Status must be one of {allowed}")
        return cleaned


class SyllabusTopicResponse(BaseModel):
    """Schema for topic response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    unit_number: int
    topic_name: str
    subtopics: list[Any] = Field(default_factory=list)
    order_index: int
    prerequisites: list[Any] = Field(default_factory=list)
    estimated_hours: float
    difficulty: int
    coverage_status: str
    coverage_confidence: float
    coverage_evidence: dict[str, Any] = Field(default_factory=dict)
    user_override_status: Optional[str] = None
    effective_status: str = Field(
        ...,
        description="Active coverage status considering user override",
    )
    created_at: datetime
    updated_at: datetime


class CoverageAnalysisResponse(BaseModel):
    """Summary of coverage analysis for a course."""

    course_id: int
    total_topics: int
    covered_count: int
    partially_covered_count: int
    not_found_count: int
    needs_review_count: int
    coverage_percentage: float = Field(
        ..., description="Percentage of topics covered or partially covered"
    )
    topics: list[SyllabusTopicResponse] = Field(default_factory=list)
