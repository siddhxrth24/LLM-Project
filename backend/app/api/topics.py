from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import SyllabusTopic, TopicContent
from app.schemas.topic import (
    LessonContent,
    SourceReference,
    TopicContentGenerateRequest,
    TopicContentResponse,
)
from app.services.teaching_service import (
    generate_topic_content as svc_generate_content,
)
from app.services.teaching_service import (
    get_topic_content as svc_get_content,
)

router = APIRouter(prefix="/api/topics", tags=["topics"])


def _to_content_response(record: TopicContent, topic_name: str) -> TopicContentResponse:
    content_obj = LessonContent.model_validate(record.content_json)
    refs_list = [SourceReference.model_validate(r) for r in (record.source_refs or [])]

    return TopicContentResponse(
        id=record.id,
        topic_id=record.topic_id,
        topic_name=topic_name,
        content=content_obj,
        source_refs=refs_list,
        generated_at=record.generated_at,
        model_used=record.model_used,
    )


@router.post("/generate/{topic_id}", response_model=TopicContentResponse)
async def generate_lesson(
    topic_id: int,
    payload: Optional[TopicContentGenerateRequest] = None,
    db: Session = Depends(get_db),
) -> TopicContentResponse:
    """Generate structured teaching content for a syllabus topic using offline LLM and RAG grounding."""
    topic = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id).first()
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Syllabus topic {topic_id} not found",
        )

    regenerate = payload.regenerate if payload else False
    record = svc_generate_content(topic_id=topic_id, db=db, regenerate=regenerate)
    return _to_content_response(record, topic.topic_name)


@router.get("/{topic_id}/content", response_model=TopicContentResponse)
async def get_lesson(
    topic_id: int,
    db: Session = Depends(get_db),
) -> TopicContentResponse:
    """Retrieve saved lesson content for a syllabus topic."""
    topic = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id).first()
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Syllabus topic {topic_id} not found",
        )

    record = svc_get_content(topic_id=topic_id, db=db)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content for topic '{topic.topic_name}' has not been generated yet. Call POST /api/topics/generate/{topic_id} first.",
        )

    return _to_content_response(record, topic.topic_name)
