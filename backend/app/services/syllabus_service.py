import math
import re
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.logging_config import logger
from app.models.models import Course, SyllabusTopic
from app.schemas.syllabus import (
    CoverageAnalysisResponse,
    SyllabusTopicResponse,
)
from app.services.llm_service import get_llm_service
from app.services.retrieval_service import hybrid_search


class SyllabusLLMUnavailableError(RuntimeError):
    """Raised when syllabus parsing is requested but no local LLM is available."""


class LLMParsedTopic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_number: int = Field(..., ge=1, le=5)
    topic_name: str = Field(..., min_length=1, max_length=255)
    subtopics: list[str] = Field(..., max_length=100)
    prerequisites: list[str] = Field(..., max_length=100)
    estimated_hours: float = Field(..., gt=0.0, le=50.0)
    difficulty: int = Field(..., ge=1, le=5)


class LLMSyllabusStructure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topics: list[LLMParsedTopic] = Field(..., max_length=100)


class LLMCoverageClassification(BaseModel):
    status: str = Field(
        ...,
        description="'covered', 'partially_covered', 'not_found', or 'needs_review'",
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_summary: str = Field(default="")
    key_matching_points: list[str] = Field(default_factory=list)


_TABLE_TOPIC_MARKER = re.compile(r"(?im)^\s*U([1-5])\s*[-–—]\s*T\s*(\d+)\b")
_UNIT_HEADING = re.compile(
    r"(?im)^\s*(?:Unit|Module|Chapter|Part)\s+(?:No\.?\s*)?"
    r"(1|2|3|4|5|I{1,3}|IV|V)\b[^\r\n]*$|^\s*U([1-5])\s*$"
)


def _unit_number(label: str) -> int:
    if label.isdigit():
        return int(label)
    return {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}[label.upper()]


def _split_syllabus_units(syllabus_text: str) -> list[tuple[int | None, str]]:
    """Split long syllabus source into bounded LLM requests, one unit at a time."""
    headings = list(_UNIT_HEADING.finditer(syllabus_text))
    if headings:
        sections: list[tuple[int | None, str]] = []
        for index, heading in enumerate(headings):
            label = heading.group(1) or heading.group(2)
            end = headings[index + 1].start() if index + 1 < len(headings) else len(syllabus_text)
            sections.append((_unit_number(label), syllabus_text[heading.start():end].strip()))
        return sections

    markers = list(_TABLE_TOPIC_MARKER.finditer(syllabus_text))
    if not markers:
        return [(None, syllabus_text)]

    starts: list[tuple[int, int]] = []
    previous_unit: int | None = None
    for marker in markers:
        unit_number = int(marker.group(1))
        if unit_number != previous_unit:
            starts.append((unit_number, marker.start()))
            previous_unit = unit_number
    return [
        (
            unit_number,
            syllabus_text[start:end].strip(),
        )
        for index, (unit_number, start) in enumerate(starts)
        for end in [starts[index + 1][1] if index + 1 < len(starts) else len(syllabus_text)]
    ]


def extract_unit_related_text(syllabus_text: str) -> str:
    """Keep the unit content source intact for the LLM parser, removing other sections."""
    if not _TABLE_TOPIC_MARKER.search(syllabus_text):
        return syllabus_text.strip()

    text = syllabus_text
    course_content = re.search(r"(?im)^\s*Course\s+Content\s*$", text)
    if course_content:
        text = text[course_content.start():]

    section_end = re.search(
        r"(?im)^\s*(?:Text\s*&\s*Reference\s+Books|Examination\s+Pattern)\b",
        text,
    )
    if section_end:
        text = text[:section_end.start()]

    return text.strip()


def _parse_coded_unit_topics(syllabus_text: str) -> list[LLMParsedTopic]:
    """Read U1-T1 curriculum rows and ignore unrelated syllabus sections."""
    matches = list(_TABLE_TOPIC_MARKER.finditer(syllabus_text))
    topics: list[LLMParsedTopic] = []
    for index, match in enumerate(matches):
        unit_number = int(match.group(1))
        end = matches[index + 1].start() if index + 1 < len(matches) else len(syllabus_text)
        row_text = syllabus_text[match.end():end]
        row_text = re.sub(r"(?im)^\s*(?:Topic\s+No\.?|Content|Description|Topic\s+Reference|Material\s+Upload)\s*$", " ", row_text)
        row_text = re.sub(r"(?m)^\s*[-–—]\s*$", " ", row_text)
        row_text = re.sub(r"(?<=\w)-\s*\r?\n\s*(?=\w)", "-", row_text)
        row_text = re.sub(r"\s+", " ", row_text).strip(" -–—:;,.\t")

        # Curriculum content is conventionally dash-separated; the first item
        # is the topic and following items are its syllabus subtopics. The
        # comma-heavy final cell in these tables is the adjacent Description column.
        content_items = [
            item.strip(" -–—:;,.\t")
            for item in re.split(r"\s+[-–—]\s+", row_text)
            if item.strip(" -–—:;,.\t")
        ]
        if content_items and content_items[-1].count(",") >= 2:
            content_items.pop()
        if not content_items:
            continue

        topic_name = content_items[0]
        if len(topic_name) > 255:
            topic_name = topic_name[:255].rstrip()
        subtopics = list(dict.fromkeys(item[:255] for item in content_items[1:] if item))
        topics.append(
            LLMParsedTopic(
                unit_number=unit_number,
                topic_name=topic_name,
                subtopics=subtopics[:100],
                prerequisites=[],
                estimated_hours=2.0,
                difficulty=3,
            )
        )
    return topics


def parse_syllabus_heuristic(syllabus_text: str) -> list[LLMParsedTopic]:
    """
    Regex-based heuristic fallback parser for syllabus text.
    Handles 'Unit 1', 'Module 1', roman numerals, and numbered/bulleted topics.
    """
    coded_topics = _parse_coded_unit_topics(syllabus_text)
    if coded_topics:
        return coded_topics

    lines = [line.strip() for line in syllabus_text.splitlines() if line.strip()]
    topics: list[LLMParsedTopic] = []

    current_unit = 1
    roman_map = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}

    for line in lines:
        # Detect unit header: "Unit 1:", "Module II -", etc.
        unit_match = re.match(
            r"^(?:Unit|Module|Chapter|Part)\s+(?:No\.?\s*)?([0-9]+|[IVX]+)\s*[:.\-–—]?\s*(.*)$",
            line,
            re.IGNORECASE,
        )
        if unit_match:
            u_str = unit_match.group(1).upper()
            if u_str.isdigit():
                current_unit = int(u_str)
            elif u_str in roman_map:
                current_unit = roman_map[u_str]
            else:
                raise ValueError(f"Unsupported syllabus unit number '{u_str}'. Use units 1 to 5.")
            if not 1 <= current_unit <= 5:
                raise ValueError(
                    f"Syllabus unit number {current_unit} is outside the supported range 1 to 5."
                )
            remainder = unit_match.group(2).strip()
            if remainder and len(remainder) > 3:
                # Header also includes topic name
                topics.append(
                    LLMParsedTopic(
                        unit_number=current_unit,
                        topic_name=remainder,
                        subtopics=[],
                        prerequisites=[],
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
                        prerequisites=[],
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
                    prerequisites=[],
                    estimated_hours=2.0,
                    difficulty=3,
                )
            )

    return topics


def parse_syllabus_topics(syllabus_text: str) -> list[LLMParsedTopic]:
    """Parse syllabus text into validated topic data using the configured local LLM."""
    if not syllabus_text or not syllabus_text.strip():
        raise ValueError("Syllabus text cannot be empty.")

    syllabus_text = extract_unit_related_text(syllabus_text)

    llm = get_llm_service()
    if not llm.is_loaded() and not llm.load_model():
        raise SyllabusLLMUnavailableError(
            "The local language model is unavailable. Download the configured model and "
            "load it from Settings before parsing a syllabus."
        )

    parsed_topics: list[LLMParsedTopic] = []
    unit_sections = _split_syllabus_units(syllabus_text)
    for unit_number, unit_text in unit_sections:
        prompt = (
            "ROLE: You are a precise academic syllabus data parser. Do not teach, summarize, "
            "or add facts. Extract source content only.\n\n"
            "SCOPE: The supplied text contains one unit section. Read the Topic No. and Content "
            "columns. Ignore Course Outcomes, course details, credits, Unit Teaching Hours, "
            "Development Needs, Skill Focus, Cross Cutting Issues, Reference Link, the adjacent "
            "Description column, textbooks, and exam sections. Do not treat learning outcomes "
            "or descriptions as syllabus topics.\n\n"
            "EXTRACTION RULES:\n"
            "1. Return one topic object for each Ux-Ty curriculum row, in source order. Do not "
            "merge separate rows or omit any row.\n"
            "2. Put the main subject of the Content cell in topic_name. Put every remaining "
            "dash-separated Content item in subtopics, preserving wording and source order. "
            "Do not truncate the list.\n"
            "3. Set unit_number to the unit number given below for every topic.\n"
            "4. Include all six keys on every object: unit_number, topic_name, subtopics, "
            "prerequisites, estimated_hours, difficulty. Use no additional keys.\n"
            "5. prerequisites must contain only clearly stated prerequisite topic names; use "
            "an empty list when the source does not state any. Do not infer prerequisites.\n"
            "6. estimated_hours must be greater than 0 and at most 50. Use the unit hours "
            "only if the source supplies them; otherwise estimate the topic workload.\n"
            "7. difficulty must be an integer from 1 (easiest) to 5 (hardest), based on the "
            "listed concepts.\n"
            "8. Return an empty topics list only when this unit has no Topic No. rows.\n\n"
            "OUTPUT FORMAT: Return only this JSON shape, with every key present:\n"
            '{"topics":[{"unit_number":1,"topic_name":"Topic title","subtopics":'
            '["Subtopic one","Subtopic two"],"prerequisites":[],"estimated_hours":2.0,'
            '"difficulty":3}]}\n\n'
            f"UNIT NUMBER: {unit_number if unit_number is not None else 'read from source'}\n"
            f"UNIT SOURCE:\n{unit_text}\n"
        )
        structured = llm.generate_structured(
            prompt,
            LLMSyllabusStructure,
            max_retries=2,
            compact_output=False,
        )
        if unit_number is not None and any(
            topic.unit_number != unit_number for topic in structured.topics
        ):
            raise ValueError(
                f"The LLM assigned a topic to the wrong unit while parsing Unit {unit_number}. "
                "Please try again or correct the unit heading."
            )
        parsed_topics.extend(structured.topics)

    logger.info(f"LLM successfully extracted {len(parsed_topics)} topics from syllabus.")

    if not parsed_topics:
        raise ValueError(
            "No syllabus topics could be recognized. Add unit headings and topic names, "
            "for example 'Unit 1: Foundations' or '- Topic name'."
        )

    # Validate and normalize generated output before replacing any existing topics.
    cleaned_topics: list[LLMParsedTopic] = []
    seen: set[tuple[int, str]] = set()
    for topic in parsed_topics:
        name = " ".join(topic.topic_name.split()).strip(" -–—:;,.\t")
        if not name:
            continue
        if len(name) > 255:
            name = name[:255].rstrip()
        if not math.isfinite(topic.estimated_hours):
            continue
        key = (topic.unit_number, name.casefold())
        if key in seen:
            continue
        seen.add(key)
        subtopics = list(
            dict.fromkeys(
                cleaned
                for value in topic.subtopics
                if isinstance(value, str)
                if (cleaned := " ".join(value.split()).strip())
            )
        )
        cleaned_topics.append(
            topic.model_copy(update={"topic_name": name, "subtopics": subtopics})
        )

    if not cleaned_topics:
        raise ValueError(
            "The syllabus parser did not return any usable topic names. "
            "Review the syllabus and try again."
        )

    return cleaned_topics


def parse_syllabus(
    syllabus_text: str,
    course_id: int,
    db: Session,
) -> list[SyllabusTopic]:
    """Parse syllabus text with the local LLM and replace the course's saved topics."""
    cleaned_topics = parse_syllabus_topics(syllabus_text)
    syllabus_text = extract_unit_related_text(syllabus_text)

    # Clean existing syllabus topics for course
    db.query(SyllabusTopic).filter(SyllabusTopic.course_id == course_id).delete()

    created_topics: list[SyllabusTopic] = []
    for idx, pt in enumerate(cleaned_topics):
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
