import io
from fastapi.testclient import TestClient

from app.models.models import Course, SyllabusTopic


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


def test_system_settings_and_missing_model_handling(client: TestClient, test_course: Course) -> None:
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
