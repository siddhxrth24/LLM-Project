from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Course(Base):
    """Course entity containing units, documents, syllabus topics, and schedules."""

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    syllabus_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exam_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    study_days_per_week: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    daily_study_hours: Mapped[float] = mapped_column(Float, default=2.0, nullable=False)
    difficulty_preference: Mapped[str] = mapped_column(
        String(50), default="balanced", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    units: Mapped[list["Unit"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Unit.unit_number",
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
    )
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
    )
    topics: Mapped[list["SyllabusTopic"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="SyllabusTopic.order_index",
    )
    study_sessions: Mapped[list["StudySession"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="StudySession.order_index",
    )


class Unit(Base):
    """Unit representation for a course (typically Units 1 to 5)."""

    __tablename__ = "units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    unit_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    course: Mapped["Course"] = relationship(back_populates="units")
    documents: Mapped[list["Document"]] = relationship(
        back_populates="unit",
        cascade="all, delete-orphan",
    )
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="unit",
        cascade="all, delete-orphan",
    )


class Document(Base):
    """Uploaded study material file (PDF or PPTX)."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("units.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)  # pdf / pptx
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False
    )  # pending, processing, completed, failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    unit: Mapped["Unit"] = relationship(back_populates="documents")
    course: Mapped["Course"] = relationship(back_populates="documents")
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class Chunk(Base):
    """Text chunk extracted from a document with vector and full-text references."""

    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    unit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("units.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    slide_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="chunks")
    course: Mapped["Course"] = relationship(back_populates="chunks")
    unit: Mapped["Unit"] = relationship(back_populates="chunks")


class SyllabusTopic(Base):
    """Structured topic extracted from syllabus."""

    __tablename__ = "syllabus_topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    unit_number: Mapped[int] = mapped_column(Integer, nullable=False)
    topic_name: Mapped[str] = mapped_column(String(255), nullable=False)
    subtopics: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    prerequisites: Mapped[list[Any]] = mapped_column(
        JSON, default=list, nullable=False
    )
    estimated_hours: Mapped[float] = mapped_column(Float, default=2.0, nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, default=3, nullable=False)  # 1-5
    coverage_status: Mapped[str] = mapped_column(
        String(50), default="not_found", nullable=False
    )  # covered, partially_covered, not_found, needs_review
    coverage_confidence: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )
    coverage_evidence: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    user_override_status: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    course: Mapped["Course"] = relationship(back_populates="topics")
    study_sessions: Mapped[list["StudySession"]] = relationship(
        back_populates="topic",
        cascade="all, delete-orphan",
    )
    content: Mapped[Optional["TopicContent"]] = relationship(
        back_populates="topic",
        uselist=False,
        cascade="all, delete-orphan",
    )


class StudySession(Base):
    """Scheduled study or revision session."""

    __tablename__ = "study_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    topic_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("syllabus_topics.id", ondelete="SET NULL"), nullable=True
    )
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    duration_hours: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    session_type: Mapped[str] = mapped_column(
        String(50), default="study", nullable=False
    )  # study, revision
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    course: Mapped["Course"] = relationship(back_populates="study_sessions")
    topic: Mapped[Optional["SyllabusTopic"]] = relationship(
        back_populates="study_sessions"
    )


class TopicContent(Base):
    """Generated teaching lesson content grounded in uploaded documents."""

    __tablename__ = "topic_contents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("syllabus_topics.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    content_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    source_refs: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    model_used: Mapped[str] = mapped_column(
        String(100), default="Qwen/Qwen3.5-0.8B", nullable=False
    )

    # Relationships
    topic: Mapped["SyllabusTopic"] = relationship(back_populates="content")
