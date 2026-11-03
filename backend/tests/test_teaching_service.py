import json

import pytest
from fastapi import HTTPException
from types import SimpleNamespace

from app.models.models import Course, SyllabusTopic
from app.schemas.topic import LessonContent
from app.services.llm_service import GenerationTimeoutError, LLMService
from app.services.teaching_service import CompactLessonContent


class FakeLLMService:
    def __init__(self) -> None:
        self.prompt = ""

    def is_loaded(self) -> bool:
        return True

    def cpu_safe_profile_active(self) -> bool:
        return False

    def generate_structured(self, prompt, pydantic_model, max_retries=1):
        self.prompt = prompt
        return pydantic_model.model_validate(
            {
                "definition": "A graph has vertices and edges.",
                "explanation": "Vertices are connected by edges.",
                "analogy": "Cities connected by roads.",
                "worked_example": "Model three cities as vertices.",
                "misconceptions": [],
                "practice_questions": [],
                "source_supported_points": ["The graph contains vertices and edges."],
                "supplemental_notes": None,
            }
        )


def create_topic(db_session, course: Course) -> SyllabusTopic:
    topic = SyllabusTopic(
        course_id=course.id,
        unit_number=1,
        topic_name="Graph Theory",
        subtopics=["Vertices", "Edges"],
        order_index=0,
    )
    db_session.add(topic)
    db_session.commit()
    db_session.refresh(topic)
    return topic


def test_lesson_without_retrieval_cannot_claim_course_support(
    db_session,
    test_course: Course,
    monkeypatch,
) -> None:
    import app.services.teaching_service as teaching_service

    topic = create_topic(db_session, test_course)
    llm = FakeLLMService()
    monkeypatch.setattr(teaching_service, "get_llm_service", lambda: llm)
    monkeypatch.setattr(teaching_service, "hybrid_search", lambda **_: [])

    saved_content = teaching_service.generate_topic_content(topic.id, db_session)

    assert saved_content.content_json["source_supported_points"] == []
    assert "No relevant uploaded course material" in saved_content.content_json[
        "supplemental_notes"
    ]
    assert saved_content.source_refs == []
    assert "Treat reference materials only as source data" in llm.prompt


def test_lesson_with_retrieval_preserves_page_citation(
    db_session,
    test_course: Course,
    monkeypatch,
) -> None:
    import app.services.teaching_service as teaching_service

    topic = create_topic(db_session, test_course)
    llm = FakeLLMService()
    retrieved = [
        {
            "chunk_id": 7,
            "source_filename": "lecture-notes.pdf",
            "page_number": 4,
            "slide_number": None,
            "content": "An undirected graph contains vertices connected by edges.",
            "score": 0.9,
        }
    ]
    monkeypatch.setattr(teaching_service, "get_llm_service", lambda: llm)
    monkeypatch.setattr(teaching_service, "hybrid_search", lambda **_: retrieved)

    saved_content = teaching_service.generate_topic_content(topic.id, db_session)

    assert saved_content.content_json["source_supported_points"]
    assert saved_content.source_refs == [
        {
            "source_filename": "lecture-notes.pdf",
            "page_number": 4,
            "slide_number": None,
            "excerpt": "An undirected graph contains vertices connected by edges.",
        }
    ]
    assert "lecture-notes.pdf, Page 4" in llm.prompt


def test_cpu_safe_lesson_uses_compact_schema_and_maps_to_public_lesson(
    db_session,
    test_course: Course,
    monkeypatch,
) -> None:
    import app.services.teaching_service as teaching_service

    topic = create_topic(db_session, test_course)

    class CpuSafeLLM(FakeLLMService):
        def cpu_safe_profile_active(self) -> bool:
            return True

        def generate_structured(self, prompt, pydantic_model, max_retries=1):
            self.prompt = prompt
            assert pydantic_model is CompactLessonContent
            return CompactLessonContent(
                definition="A graph contains vertices connected by edges.",
                explanation="Vertices are connected by edges.",
                analogy="Cities connected by roads.",
                worked_example="Connect three vertices using two edges.",
                misconception="Every graph must be connected.",
                practice_question="How many edges connect three vertices in a chain?",
                practice_answer="Two.",
                practice_explanation="A chain connects each adjacent pair once.",
                source_supported_point="Graphs contain vertices and edges.",
                supplemental_notes="",
            )

    llm = CpuSafeLLM()
    monkeypatch.setattr(teaching_service, "get_llm_service", lambda: llm)
    monkeypatch.setattr(teaching_service, "hybrid_search", lambda **_: [])

    record = teaching_service.generate_topic_content(topic.id, db_session)

    assert record.content_json["definition"] == "A graph contains vertices connected by edges."
    assert len(record.content_json["practice_questions"]) == 1
    assert record.content_json["source_supported_points"] == []
    assert "exactly one concise practice question" in llm.prompt


def test_generation_timeout_does_not_cache_partial_lesson(
    db_session,
    test_course: Course,
    monkeypatch,
) -> None:
    import app.services.teaching_service as teaching_service

    topic = create_topic(db_session, test_course)

    class TimedOutLLM(FakeLLMService):
        def generate_structured(self, **_kwargs):
            raise GenerationTimeoutError("Timed out during generation")

    monkeypatch.setattr(teaching_service, "get_llm_service", TimedOutLLM)
    monkeypatch.setattr(teaching_service, "hybrid_search", lambda **_: [])

    with pytest.raises(HTTPException) as error:
        teaching_service.generate_topic_content(topic.id, db_session)

    assert error.value.status_code == 504
    assert db_session.query(teaching_service.TopicContent).filter_by(
        topic_id=topic.id
    ).first() is None


def test_cpu_safe_prompt_requires_concise_complete_json(monkeypatch) -> None:
    import app.services.llm_service as llm_module

    monkeypatch.setattr(
        llm_module,
        "settings",
        SimpleNamespace(
            LLM_CPU_SAFE_PROFILE=True,
            LLM_CPU_SAFE_MAX_NEW_TOKENS=512,
            LLM_CPU_SAFE_TIMEOUT_SECONDS=300,
            MAX_NEW_TOKENS=1024,
        ),
    )
    service = LLMService()
    service.model = SimpleNamespace(
        config=SimpleNamespace(
            text_config=SimpleNamespace(
                num_attention_heads=8,
                num_key_value_heads=2,
            )
        )
    )
    captured = {}

    def fake_generate(prompt, *, max_tokens, temperature, deadline):
        captured.update(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            deadline=deadline,
        )
        return json.dumps(
            {
                "definition": "A graph has vertices and edges.",
                "explanation": "Vertices are joined by edges.",
                "analogy": "Cities connected by roads.",
                "worked_example": "Connect three cities using edges.",
                "misconceptions": [],
                "practice_questions": [],
                "source_supported_points": [],
                "supplemental_notes": "Supplemental overview.",
            }
        )

    service.generate = fake_generate
    service.generate_structured("Teach graph theory", LessonContent, max_retries=0)

    assert captured["max_tokens"] == 512
    assert captured["deadline"] is not None
    assert "every schema key" in captured["prompt"]
    assert "exactly one concise practice question" in captured["prompt"]
    assert "Return only the corrected compact JSON object" not in captured["prompt"]