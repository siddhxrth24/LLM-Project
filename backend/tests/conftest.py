from collections.abc import Generator
from datetime import date
import os
from pathlib import Path
import tempfile
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Keep app lifespan initialization and upload tests away from the developer's data directory.
_TEST_RUNTIME = tempfile.TemporaryDirectory(prefix="semestrack-tests-")
_TEST_RUNTIME_DIR = Path(_TEST_RUNTIME.name)
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["UPLOAD_DIR"] = str(_TEST_RUNTIME_DIR / "uploads")
os.environ["CHROMA_DIR"] = str(_TEST_RUNTIME_DIR / "chroma")

from app.core.database import Base, get_db
from app.main import app
from app.models.models import Course, Unit

# In-memory SQLite with StaticPool ensures multiple connections share the exact same in-memory DB
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
    expire_on_commit=False,
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db() -> Generator[None, None, None]:
    """Create all tables and FTS5 index in the in-memory test database."""
    Base.metadata.create_all(bind=test_engine)
    with test_engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS document_fts USING fts5(
                    chunk_id UNINDEXED,
                    course_id UNINDEXED,
                    unit_id UNINDEXED,
                    source_filename UNINDEXED,
                    page_number UNINDEXED,
                    content,
                    tokenize='porter unicode61'
                );
                """
            )
        )
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a transactional database session fixture."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient wired to override get_db with the test database session."""
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_course(db_session: Session) -> Course:
    """Fixture creating a ready-to-use sample Course with units."""
    course = Course(
        name="Operating Systems",
        syllabus_text="Unit 1: Process Management\nUnit 2: Memory Management",
        exam_date=date(2026, 12, 10),
        study_days_per_week=5,
        daily_study_hours=2.0,
        difficulty_preference="balanced",
    )
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)

    for i in range(1, 6):
        unit = Unit(
            course_id=course.id,
            unit_number=i,
            name=f"Unit {i}",
        )
        db_session.add(unit)

    db_session.commit()
    db_session.refresh(course)
    return course
