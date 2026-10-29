import re
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.logging_config import logger
from app.models.models import Course, SyllabusTopic
from app.schemas.syllabus import (
    CoverageAnalysisResponse,
    SyllabusTopicResponse,
)
from app.services.llm_service import get_llm_service
from app.services.retrieval_service import hybrid_search


class LLMParsedTopic(BaseModel):
    unit_number: int = Field(default=1, ge=1, le=10)
    topic_name: str
    subtopics: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    estimated_hours: float = Field(default=2.0, gt=0.0)
    difficulty: int = Field(default=3, ge=1, le=5)


class LLMSyllabusStructure(BaseModel):
    topics: list[LLMParsedTopic] = Field(default_factory=list)


class LLMCoverageClassification(BaseModel):
    status: str = Field(
        ...,
        description="'covered', 'partially_covered', 'not_found', or 'needs_review'",
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_summary: str = Field(default="")
    key_matching_points: list[str] = Field(default_factory=list)


def parse_syllabus_heuristic(syllabus_text: str) -> list[LLMParsedTopic]:
    """
    Regex-based heuristic fallback parser for syllabus text.
    Handles 'Unit 1', 'Module 1', roman numerals, and numbered/bulleted topics.
    """
    lines = [line.strip() for line in syllabus_text.splitlines() if line.strip()]
    topics: list[LLMParsedTopic] = []

    current_unit = 1
    roman_map = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}

    for line in lines:
        # Detect unit header: "Unit 1:", "Module II -", etc.
        unit_match = re.match(
            r"^(?:Unit|Module|Chapter|Part)\s+([0-9IVX]+)[\s:.-]*(.*)$",
            line,
            re.IGNORECASE,
        )
        if unit_match:
            u_str = unit_match.group(1).upper()
            if u_str.isdigit():
                current_unit = int(u_str)
            elif u_str in roman_map:
                current_unit = roman_map[u_str]
            remainder = unit_match.group(2).strip()
            if remainder and len(remainder) > 3:
                # Header also includes topic name
                topics.append(
                    LLMParsedTopic(
                        unit_number=current_unit,
                        topic_name=remainder,
                        subtopics=[],
                        estimated_hours=2.0,
                        difficulty=3,
                    )
                )
            continue

        # Detect topic bullet points or numbered entries: "1. Topic", "- Topic"
        bullet_match = re.match(r"^(?:[-*•]|\d+[\.\)])\s*(.*)$", line)
        if bullet_match:
            item_text = bullet_match.group(1).strip()
            if len(item_text) > 3:
                # Check if it has subtopics separated by comma/semicolon/colons
                sub_parts = [p.strip() for p in re.split(r"[,;:]", item_text) if len(p.strip()) > 2]
                topic_title = sub_parts[0] if sub_parts else item_text
                subtopics = sub_parts[1:] if len(sub_parts) > 1 else []

                topics.append(
                    LLMParsedTopic(
                        unit_number=current_unit,
                        topic_name=topic_title,
                        subtopics=subtopics,
                        estimated_hours=2.0,
                        difficulty=3,
                    )
                )
            continue

        # If a plain line has reasonable length, consider it a topic
        if 4 < len(line) < 120 and not line.endswith(":"):
            sub_parts = [p.strip() for p in re.split(r"[,;]", line) if len(p.strip()) > 2]
            topic_title = sub_parts[0] if sub_parts else line
            subtopics = sub_parts[1:] if len(sub_parts) > 1 else []
            topics.append(
                LLMParsedTopic(
                    unit_number=current_unit,
                    topic_name=topic_title,
                    subtopics=subtopics,
                    estimated_hours=2.0,
                    difficulty=3,
                )
            )

    return topics


def parse_syllabus(
    syllabus_text: str,
    course_id: int,
    db: Session,
) -> list[SyllabusTopic]:
    """
    Parse unstructured syllabus text into structured SyllabusTopic database records.
    Uses LLM structured generation when available, falling back to heuristic parsing.
    """
    llm = get_llm_service()
    parsed_topics: list[LLMParsedTopic] = []

    if llm.is_loaded():
        prompt = (
            "You are an academic curriculum parser. Extract all topics and subtopics from the syllabus text below.\n"
            "Group topics into unit numbers (1 to 5). Estimate study hours (1.0 to 6.0) and difficulty (1=easiest to 5=hardest).\n"
            "Identify prerequisites by name if earlier topics are clearly required.\n\n"
            f"Syllabus Text:\n{syllabus_text}\n"
        )
        try:
            structured = llm.generate_structured(prompt, LLMSyllabusStructure, max_retries=1)
            parsed_topics = structured.topics
            logger.info(f"LLM successfully extracted {len(parsed_topics)} topics from syllabus.")
        except Exception as exc:
            logger.warning(f"LLM syllabus extraction failed ({exc}); falling back to heuristic parser.")

    if not parsed_topics:
        parsed_topics = parse_syllabus_heuristic(syllabus_text)
        logger.info(f"Heuristic parser extracted {len(parsed_topics)} topics.")

    # Fallback default if completely empty
    if not parsed_topics:
        parsed_topics = [
            LLMParsedTopic(
                unit_number=1,
                topic_name="Course Overview & Core Concepts",
                subtopics=["Fundamental definitions", "Foundational principles"],
                estimated_hours=2.0,
                difficulty=2,
            )
        ]

    # Clean existing syllabus topics for course
    db.query(SyllabusTopic).filter(SyllabusTopic.course_id == course_id).delete()

    created_topics: list[SyllabusTopic] = []
    for idx, pt in enumerate(parsed_topics):
        topic_record = SyllabusTopic(
            course_id=course_id,
            unit_number=pt.unit_number,
            topic_name=pt.topic_name,
            subtopics=pt.subtopics,
            order_index=idx,
            prerequisites=pt.prerequisites,
            estimated_hours=pt.estimated_hours,
            difficulty=pt.difficulty,
            coverage_status="not_found",
            coverage_confidence=0.0,
            coverage_evidence={},
        )
        db.add(topic_record)
        created_topics.append(topic_record)

    # Save raw syllabus text to course
    course = db.query(Course).filter(Course.id == course_id).first()
    if course:
        course.syllabus_text = syllabus_text

    db.commit()
    for t in created_topics:
        db.refresh(t)

    return created_topics


def analyze_coverage(course_id: int, db: Session) -> CoverageAnalysisResponse:
    """
    Evaluate study material coverage for each syllabus topic in a course.
    Runs hybrid retrieval against uploaded documents and applies LLM or heuristic classification.
    """
    topics = (
        db.query(SyllabusTopic)
        .filter(SyllabusTopic.course_id == course_id)
        .order_by(SyllabusTopic.order_index)
        .all()
    )

    llm = get_llm_service()

    for topic in topics:
        subtopics_str = " ".join(str(s) for s in (topic.subtopics or []))
        query = f"{topic.topic_name} {subtopics_str}".strip()

        # Hybrid search in course chunks
        retrieved_chunks = hybrid_search(
            db=db,
            query=query,
            course_id=course_id,
            unit_id=None,
            top_k=5,
        )

        if not retrieved_chunks:
            topic.coverage_status = "not_found"
            topic.coverage_confidence = 0.0
            topic.coverage_evidence = {"reason": "No relevant document chunks found"}
            continue

        best_score = max(c.get("score", 0.0) for c in retrieved_chunks)
        evidence_citations: list[dict[str, Any]] = [
            {
                "source_filename": c.get("source_filename"),
                "page_number": c.get("page_number"),
                "slide_number": c.get("slide_number"),
                "score": round(c.get("score", 0.0), 3),
                "snippet": c.get("content", "")[:200] + "...",
            }
            for c in retrieved_chunks[:3]
        ]

        if llm.is_loaded():
            context_text = "\n\n".join(
                f"[Source: {c.get('source_filename')}]\n{c.get('content', '')}"
                for c in retrieved_chunks[:3]
            )
            classification_prompt = (
                f"You are evaluating whether course materials cover a syllabus topic.\n"
                f"Topic: {topic.topic_name}\n"
                f"Subtopics: {topic.subtopics}\n\n"
                f"Retrieved Excerpts from Course Notes:\n{context_text}\n\n"
                f"Determine if the topic is:\n"
                f"- 'covered': concepts are thoroughly explained in the excerpts\n"
                f"- 'partially_covered': concepts are mentioned briefly or some subtopics are missing\n"
                f"- 'not_found': excerpts are unrelated\n"
                f"- 'needs_review': ambiguous or conflicting information\n"
            )
            try:
                classified = llm.generate_structured(
                    classification_prompt,
                    LLMCoverageClassification,
                    max_retries=1,
                )
                valid_statuses = {"covered", "partially_covered", "not_found", "needs_review"}
                topic.coverage_status = (
                    classified.status.lower()
                    if classified.status.lower() in valid_statuses
                    else "partially_covered"
                )
                topic.coverage_confidence = round(float(classified.confidence), 2)
                topic.coverage_evidence = {
                    "summary": classified.evidence_summary,
                    "key_points": classified.key_matching_points,
                    "citations": evidence_citations,
                }
                continue
            except Exception as exc:
                logger.warning(f"LLM coverage classification failed for topic {topic.id}: {exc}")

        # Heuristic scoring fallback
        if best_score >= 0.65:
            topic.coverage_status = "covered"
            topic.coverage_confidence = round(min(0.95, best_score), 2)
        elif best_score >= 0.35:
            topic.coverage_status = "partially_covered"
            topic.coverage_confidence = round(best_score, 2)
        elif best_score >= 0.15:
            topic.coverage_status = "needs_review"
            topic.coverage_confidence = round(best_score, 2)
        else:
            topic.coverage_status = "not_found"
            topic.coverage_confidence = 0.10

        topic.coverage_evidence = {
            "summary": f"Matched with score {round(best_score, 3)}",
            "citations": evidence_citations,
        }

    db.commit()

    # Build response summary
    return get_coverage_summary(course_id, db)


def get_coverage_summary(course_id: int, db: Session) -> CoverageAnalysisResponse:
    """Compute and format coverage statistics for a course."""
    topics = (
        db.query(SyllabusTopic)
        .filter(SyllabusTopic.course_id == course_id)
        .order_by(SyllabusTopic.order_index)
        .all()
    )

    total = len(topics)
    covered = 0
    partially = 0
    not_found = 0
    needs_review = 0

    topic_responses: list[SyllabusTopicResponse] = []
    for t in topics:
        effective = t.user_override_status if t.user_override_status else t.coverage_status
        if effective == "covered":
            covered += 1
        elif effective == "partially_covered":
            partially += 1
        elif effective == "needs_review":
            needs_review += 1
        else:
            not_found += 1

        topic_responses.append(
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

    percentage = round(((covered + 0.5 * partially) / total * 100.0), 1) if total > 0 else 0.0

    return CoverageAnalysisResponse(
        course_id=course_id,
        total_topics=total,
        covered_count=covered,
        partially_covered_count=partially,
        not_found_count=not_found,
        needs_review_count=needs_review,
        coverage_percentage=percentage,
        topics=topic_responses,
    )


def update_topic_status(
    topic_id: int,
    user_status: Optional[str],
    db: Session,
) -> Optional[SyllabusTopic]:
    """Apply manual user status override to a syllabus topic."""
    topic = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id).first()
    if not topic:
        return None

    topic.user_override_status = user_status
    db.commit()
    db.refresh(topic)
    return topic
