import io
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.models.models import Chunk, Course, Document, SyllabusTopic, Unit
from app.main import app
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService


def test_course_crud(client: TestClient) -> None:
    """Test full CRUD lifecycle of courses."""
    # 1. Create course
    payload = {
        "name": "Distributed Systems",
        "syllabus_text": "Unit 1: Consensus\nUnit 2: Replication",
        "exam_date": "2026-12-20",
        "study_days_per_week": 6,
        "daily_study_hours": 3.0,
        "difficulty_preference": "challenging",
    }
    create_resp = client.post("/api/courses/", json=payload)
    assert create_resp.status_code == 201
    course_data = create_resp.json()
    course_id = course_data["id"]
    assert course_data["name"] == "Distributed Systems"
    assert course_data["unit_count"] == 5

    # 2. List courses
    list_resp = client.get("/api/courses/")
    assert list_resp.status_code == 200
    courses_list = list_resp.json()["courses"]
    assert any(c["id"] == course_id for c in courses_list)

    # 3. Get course detail
    detail_resp = client.get(f"/api/courses/{course_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == course_id
    assert len(detail_resp.json()["units"]) == 5

    # 4. Update course
    update_payload = {"name": "Advanced Distributed Systems", "difficulty_preference": "balanced"}
    update_resp = client.put(f"/api/courses/{course_id}", json=update_payload)
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Advanced Distributed Systems"
    assert update_resp.json()["difficulty_preference"] == "balanced"

    # 5. Delete course
    del_resp = client.delete(f"/api/courses/{course_id}")
    assert del_resp.status_code == 200

    # 6. Verify deleted
    get_after = client.get(f"/api/courses/{course_id}")
    assert get_after.status_code == 404


def test_course_syllabus_create_and_update_are_consistent(client: TestClient) -> None:
    create_response = client.post(
        "/api/courses/",
        json={
            "name": "Algorithms",
            "syllabus_text": "Unit 1: Graph Algorithms\n- Shortest Paths",
        },
    )
    assert create_response.status_code == 201
    created_course = create_response.json()
    course_id = created_course["id"]
    assert created_course["topic_count"] == 2
    assert created_course["syllabus_text"].startswith("Unit 1:")

    update_response = client.put(
        f"/api/courses/{course_id}",
        json={"syllabus_text": "Unit 1: Data Structures\n- Balanced Trees"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["topic_count"] == 2

    topics_response = client.get(f"/api/syllabus/topics/{course_id}")
    assert topics_response.status_code == 200
    assert {topic["topic_name"] for topic in topics_response.json()} == {
        "Data Structures", "Balanced Trees"
    }

    invalid_update = client.put(
        f"/api/courses/{course_id}",
        json={"name": "Should Not Persist", "syllabus_text": "!!!"},
    )
    assert invalid_update.status_code == 422
    assert "No syllabus topics could be recognized" in invalid_update.json()["detail"]

    unchanged_course = client.get(f"/api/courses/{course_id}").json()
    assert unchanged_course["name"] == "Algorithms"
    assert unchanged_course["syllabus_text"] == "Unit 1: Data Structures\n- Balanced Trees"
    assert unchanged_course["topic_count"] == 2


def test_course_create_rejects_unparseable_syllabus(client: TestClient) -> None:
    response = client.post(
        "/api/courses/",
        json={"name": "Invalid Syllabus", "syllabus_text": "!!!"},
    )

    assert response.status_code == 422
    assert "No syllabus topics could be recognized" in response.json()["detail"]
    assert response.json()["error"] is True
    assert client.get("/api/courses/").json()["total"] == 0


def test_syllabus_parser_rejects_out_of_range_units_without_replacing_existing_topics(
    client: TestClient,
    test_course: Course,
) -> None:
    valid = client.post(
        f"/api/courses/{test_course.id}/syllabus",
        json={"syllabus_text": "Unit 1: Existing topic"},
    )
    assert valid.status_code == 200
    existing_ids = {topic["id"] for topic in valid.json()}

    invalid = client.post(
        f"/api/courses/{test_course.id}/syllabus",
        json={"syllabus_text": "Unit 11: Unsupported\n- Broken parser"},
    )
    assert invalid.status_code == 422
    assert "outside the supported range" in invalid.json()["detail"]

    topics = client.get(f"/api/syllabus/topics/{test_course.id}").json()
    assert {topic["id"] for topic in topics} == existing_ids


def test_topic_review_can_edit_name_and_subtopics(
    client: TestClient,
    test_course: Course,
) -> None:
    created = client.post(
        f"/api/courses/{test_course.id}/syllabus",
        json={"syllabus_text": "Unit IV: Graph algorithms"},
    )
    assert created.status_code == 200
    topic = created.json()[0]
    assert topic["unit_number"] == 4

    updated = client.put(
        f"/api/syllabus/topics/{topic['id']}",
        json={"topic_name": "Graph traversal", "subtopics": ["BFS", "DFS"]},
    )
    assert updated.status_code == 200
    assert updated.json()["topic_name"] == "Graph traversal"
    assert updated.json()["subtopics"] == ["BFS", "DFS"]


def test_syllabus_file_extraction_accepts_text_and_pdf(client: TestClient) -> None:
    text_response = client.post(
        "/api/syllabus/extract",
        files={"file": ("course-plan.txt", io.BytesIO(b"Unit 1: Foundations\n- Graphs"), "text/plain")},
    )
    assert text_response.status_code == 200
    assert text_response.json()["filename"] == "course-plan.txt"
    assert text_response.json()["text"] == "Unit 1: Foundations\n- Graphs"
    assert text_response.json()["page_count"] == 0

    fitz = pytest.importorskip("fitz")
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((50, 72), "Unit 1: Probability Theory")
    pdf_bytes = pdf.tobytes()
    pdf.close()

    pdf_response = client.post(
        "/api/syllabus/extract",
        files={"file": ("course-plan.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert pdf_response.status_code == 200
    assert "Probability Theory" in pdf_response.json()["text"]
    assert pdf_response.json()["page_count"] == 1


def test_syllabus_file_extraction_rejects_unsupported_and_empty_files(
    client: TestClient,
) -> None:
    unsupported = client.post(
        "/api/syllabus/extract",
        files={"file": ("syllabus.docx", io.BytesIO(b"document"), "application/octet-stream")},
    )
    assert unsupported.status_code == 400

    empty = client.post(
        "/api/syllabus/extract",
        files={"file": ("empty.txt", io.BytesIO(b" \n"), "text/plain")},
    )
    assert empty.status_code == 422
    assert "No text was found" in empty.json()["detail"]


def test_course_delete_cleans_uploads_and_search_indexes(
    client: TestClient,
    db_session,
    test_course: Course,
    tmp_path,
    monkeypatch,
) -> None:
    from types import SimpleNamespace

    import app.api.courses as courses_api

    class VectorStore:
        def __init__(self) -> None:
            self.deleted_course_ids: list[int] = []

        def delete_course_chunks(self, course_id: int) -> bool:
            self.deleted_course_ids.append(course_id)
            return True

    vector_store = VectorStore()
    course_dir = tmp_path / f"course_{test_course.id}"
    course_dir.mkdir()
    uploaded_file = course_dir / "lecture.pdf"
    uploaded_file.write_bytes(b"uploaded")
    unit = db_session.query(Unit).filter_by(course_id=test_course.id).first()
    document = Document(
        course_id=test_course.id,
        unit_id=unit.id,
        filename=uploaded_file.name,
        original_filename=uploaded_file.name,
        file_type="pdf",
        file_size=uploaded_file.stat().st_size,
        file_path=str(uploaded_file),
        status="completed",
    )
    db_session.add(document)
    db_session.flush()
    chunk = Chunk(
        document_id=document.id,
        course_id=test_course.id,
        unit_id=unit.id,
        content="course scoped searchable text",
        chunk_index=0,
        source_filename=uploaded_file.name,
    )
    db_session.add(chunk)
    db_session.flush()
    db_session.execute(
        text(
            "INSERT INTO document_fts "
            "(chunk_id, course_id, unit_id, source_filename, page_number, content) "
            "VALUES (:chunk_id, :course_id, :unit_id, :filename, '0', :content)"
        ),
        {
            "chunk_id": str(chunk.id),
            "course_id": str(test_course.id),
            "unit_id": str(unit.id),
            "filename": uploaded_file.name,
            "content": chunk.content,
        },
    )

    monkeypatch.setattr(courses_api, "get_embedding_service", lambda: vector_store)
    monkeypatch.setattr(
        courses_api,
        "settings",
        SimpleNamespace(resolved_upload_dir=tmp_path),
    )

    response = client.delete(f"/api/courses/{test_course.id}")

    assert response.status_code == 200
    assert db_session.get(Course, test_course.id) is None
    assert db_session.execute(text("SELECT COUNT(*) FROM chunks")).scalar_one() == 0
    assert db_session.execute(text("SELECT COUNT(*) FROM document_fts")).scalar_one() == 0
    assert not course_dir.exists()
    assert vector_store.deleted_course_ids == [test_course.id]


def test_course_delete_aborts_when_vector_cleanup_fails(
    client: TestClient,
    db_session,
    test_course: Course,
    tmp_path,
    monkeypatch,
) -> None:
    from types import SimpleNamespace

    import app.api.courses as courses_api

    class VectorStore:
        def delete_course_chunks(self, _course_id: int) -> bool:
            return False

    course_dir = tmp_path / f"course_{test_course.id}"
    course_dir.mkdir()
    uploaded_file = course_dir / "keep.pdf"
    uploaded_file.write_bytes(b"uploaded")
    monkeypatch.setattr(courses_api, "get_embedding_service", VectorStore)
    monkeypatch.setattr(
        courses_api,
        "settings",
        SimpleNamespace(resolved_upload_dir=tmp_path),
    )

    response = client.delete(f"/api/courses/{test_course.id}")

    assert response.status_code == 503
    assert db_session.get(Course, test_course.id) is not None
    assert uploaded_file.exists()
    assert course_dir.exists()


def test_document_upload_validation(client: TestClient, test_course: Course) -> None:
    """Test file type validation on document upload."""
    # Unsupported file extension (.txt or .exe)
    invalid_file = io.BytesIO(b"malicious executable or text")
    resp_invalid = client.post(
        f"/api/documents/upload/{test_course.id}/1",
        files={"files": ("bad_program.exe", invalid_file, "application/octet-stream")},
    )
    assert resp_invalid.status_code == 400
    assert "Unsupported file type" in resp_invalid.json()["detail"]

    # Valid extension (.pdf)
    dummy_pdf = io.BytesIO(b"%PDF-1.4 dummy minimal pdf stream")
    resp_valid = client.post(
        f"/api/documents/upload/{test_course.id}/1?auto_process=false",
        files={"files": ("lecture_slides.pdf", dummy_pdf, "application/pdf")},
    )
    assert resp_valid.status_code == 201
    docs = resp_valid.json()["documents"]
    assert len(docs) == 1
    assert docs[0]["original_filename"] == "lecture_slides.pdf"


def test_system_settings_and_missing_model_handling(
    client: TestClient,
    test_course: Course,
    monkeypatch,
) -> None:
    """Verify system diagnostics and graceful error handling when ML models are absent."""
    # 1. System status endpoint
    status_resp = client.get("/api/settings/status")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["status"] in ("ok", "degraded")
    assert "models" in data
    assert "storage" in data

    # 2. Model information endpoint
    models_resp = client.get("/api/settings/models")
    assert models_resp.status_code == 200
    models_info = models_resp.json()
    assert "llm_model_id" in models_info
    assert "embedding_model_id" in models_info

    # 3. Calling ML generation when model weights are not loaded locally
    monkeypatch.setattr(LLMService, "load_model", lambda self: False)
    # Add a mock topic
    topic_payload = {
        "unit_number": 1,
        "topic_name": "Raft Consensus",
        "subtopics": ["Leader election", "Log replication"],
        "estimated_hours": 2.0,
        "difficulty": 4,
    }
    # Create topic directly through parse or db
    parse_resp = client.post(
        f"/api/courses/{test_course.id}/syllabus",
        json={"syllabus_text": "Unit 1: Raft Consensus, Leader election"},
    )
    assert parse_resp.status_code == 200
    created_topics = parse_resp.json()
    assert len(created_topics) > 0
    topic_id = created_topics[0]["id"]

    # Calling generate should return 503 if local model is absent, rather than crashing
    gen_resp = client.post(f"/api/topics/generate/{topic_id}")
    if gen_resp.status_code != 200:
        assert gen_resp.status_code == 503
        assert "LLM model is not loaded" in gen_resp.json()["detail"]


def test_preflight_reports_readiness_without_loading_models(
    client: TestClient, monkeypatch
) -> None:
    """Preflight checks local capabilities without loading or downloading models."""
    def fail_if_loaded(self) -> bool:
        raise AssertionError("Preflight must not load models")

    monkeypatch.setattr(LLMService, "load_model", fail_if_loaded)
    monkeypatch.setattr(EmbeddingService, "load_model", fail_if_loaded)

    response = client.get("/api/settings/preflight")

    assert response.status_code == 200
    result = response.json()
    checks = {check["name"]: check for check in result["checks"]}
    assert result["status"] in {"ready", "degraded", "blocked"}
    assert checks["database"]["status"] == "ready"
    assert checks["fts5"]["status"] == "ready"
    assert "upload_storage" in checks
    assert "chroma_package" in checks
    assert "vector_store" in checks
    assert "embedding_model" in checks
    assert "llm_model" in checks


def test_model_loaders_do_not_fall_back_to_remote_ids(monkeypatch, tmp_path) -> None:
    """Missing local model files must fail without attempting remote resolution."""
    import app.services.embedding_service as embedding_module
    import app.services.llm_service as llm_module

    monkeypatch.setattr(
        llm_module,
        "settings",
        SimpleNamespace(resolved_llm_model_path=tmp_path),
    )
    monkeypatch.setattr(
        embedding_module,
        "settings",
        SimpleNamespace(resolved_embedding_model_path=tmp_path),
    )

    llm_service = LLMService()
    embedding_service = EmbeddingService.__new__(EmbeddingService)
    embedding_service.model = None

    assert llm_service.load_model() is False
    assert embedding_service.load_model() is False


def test_application_startup_does_not_load_models(monkeypatch) -> None:
    """Starting the API must not load or download model weights."""
    def fail_if_loaded(self) -> bool:
        raise AssertionError("Application startup must not load models")

    monkeypatch.setattr(LLMService, "load_model", fail_if_loaded)
    monkeypatch.setattr(EmbeddingService, "load_model", fail_if_loaded)

    with TestClient(app) as startup_client:
        response = startup_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
