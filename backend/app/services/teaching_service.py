from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging_config import logger
from app.models.models import SyllabusTopic, TopicContent
from app.schemas.topic import LessonContent, PracticeQuestion, SourceReference
from app.services.llm_service import get_llm_service
from app.services.retrieval_service import format_context, hybrid_search


def generate_topic_content(
    topic_id: int,
    db: Session,
    regenerate: bool = False,
) -> TopicContent:
    """
    Generate structured, ground-truthed lesson content for a syllabus topic.

    Steps:
    1. Check if lesson already exists (return if not regenerating)
    2. Retrieve relevant chunks via hybrid retrieval
    3. Generate structured lesson via LLM with strict Pydantic validation
    4. Distinguish source-supported points from supplemental context
    5. Persist to TopicContent database table
    """
    topic = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id).first()
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Syllabus topic {topic_id} not found",
        )

    # Return cached content if available and regeneration is not requested
    existing_record = (
        db.query(TopicContent).filter(TopicContent.topic_id == topic_id).first()
    )
    if existing_record and not regenerate:
        return existing_record

    llm = get_llm_service()
    if not llm.is_loaded():
        # Attempt lazy load
        loaded = llm.load_model()
        if not loaded:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    f"LLM model is not loaded. Model weights not found at "
                    f"'{settings.resolved_llm_model_path}'. Please download models for offline generation."
                ),
            )

    # Retrieve context chunks for topic grounding
    subtopics_text = " ".join(str(s) for s in (topic.subtopics or []))
    search_query = f"{topic.topic_name} {subtopics_text}".strip()

    retrieved_chunks = hybrid_search(
        db=db,
        query=search_query,
        course_id=topic.course_id,
        unit_id=None,
        top_k=6,
    )
    context_text = format_context(retrieved_chunks)

    source_references: list[dict[str, Any]] = [
        {
            "source_filename": c.get("source_filename", "Unknown Document"),
            "page_number": c.get("page_number"),
            "slide_number": c.get("slide_number"),
            "excerpt": c.get("content", "")[:300] + "...",
        }
        for c in retrieved_chunks
    ]

    prompt = (
        f"You are SemesTrack's master teaching assistant. Generate a high-yield, structured lesson "
        f"for university students on the topic '{topic.topic_name}'.\n\n"
        f"Topic Title: {topic.topic_name}\n"
        f"Unit Number: {topic.unit_number}\n"
        f"Subtopics: {topic.subtopics}\n\n"
        f"--- REFERENCE COURSE MATERIALS ---\n"
        f"{context_text}\n"
        f"--- END OF REFERENCES ---\n\n"
        f"Requirements:\n"
        f"1. definition: Crisp, mathematically or conceptually sound definition (1-2 sentences).\n"
        f"2. explanation: Detailed breakdown covering core mechanics and intuition.\n"
        f"3. analogy: A vivid, everyday metaphor that makes the concept unforgettable.\n"
        f"4. worked_example: Step-by-step problem and solution highlighting practical application.\n"
        f"5. misconceptions: 2 to 4 frequent student pitfalls or confusion points.\n"
        f"6. practice_questions: Exactly 3 questions, each with a complete answer and explanation.\n"
        f"7. source_supported_points: 2 to 4 statements explicitly corroborated by the reference materials.\n"
        f"8. supplemental_notes: Clear commentary on additional context or deeper theory beyond the provided slides.\n"
    )

    try:
        lesson = llm.generate_structured(
            prompt=prompt,
            pydantic_model=LessonContent,
            max_retries=1,
        )
    except Exception as exc:
        logger.error(f"Failed to generate structured lesson for topic {topic_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Teaching content generation failed: {exc}",
        )

    # Persist or update
    if existing_record:
        existing_record.content_json = lesson.model_dump()
        existing_record.source_refs = source_references
        existing_record.generated_at = datetime.utcnow()
        existing_record.model_used = settings.LLM_MODEL_ID
        db.commit()
        db.refresh(existing_record)
        return existing_record
    else:
        new_record = TopicContent(
            topic_id=topic_id,
            content_json=lesson.model_dump(),
            source_refs=source_references,
            generated_at=datetime.utcnow(),
            model_used=settings.LLM_MODEL_ID,
        )
        db.add(new_record)
        db.commit()
        db.refresh(new_record)
        return new_record


def get_topic_content(topic_id: int, db: Session) -> Optional[TopicContent]:
    """Retrieve previously generated lesson content for a topic."""
    return db.query(TopicContent).filter(TopicContent.topic_id == topic_id).first()
