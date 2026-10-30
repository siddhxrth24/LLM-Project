from datetime import date

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.database import Base, SCHEMA_VERSION, migrate_schema
from app.models.models import Chunk, Course, Document, Unit


def test_fresh_database_is_initialized_and_versioned(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    try:
        migrate_schema(engine)
        migrate_schema(engine)

        with engine.connect() as connection:
            version = connection.exec_driver_sql("PRAGMA user_version").scalar_one()
            fts_count = connection.execute(
                text("SELECT COUNT(*) FROM document_fts")
            ).scalar_one()

        assert version == SCHEMA_VERSION
        assert fts_count == 0
    finally:
        engine.dispose()


def test_unversioned_database_preserves_rows_and_backfills_fts(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        course = Course(name="Legacy Course", exam_date=date(2027, 1, 15))
        session.add(course)
        session.flush()

        unit = Unit(course_id=course.id, unit_number=1, name="Unit 1")
        session.add(unit)
        session.flush()

        document = Document(
            unit_id=unit.id,
            course_id=course.id,
            filename="lecture.pdf",
            original_filename="Lecture.pdf",
            file_type="pdf",
            file_size=12,
            file_path="lecture.pdf",
        )
        session.add(document)
        session.flush()

        session.add(
            Chunk(
                document_id=document.id,
                course_id=course.id,
                unit_id=unit.id,
                content="Legacy indexed text",
                chunk_index=0,
                source_filename="Lecture.pdf",
            )
        )
        session.commit()
        course_id = course.id

    try:
        migrate_schema(engine)

        with engine.connect() as connection:
            version = connection.exec_driver_sql("PRAGMA user_version").scalar_one()
            saved_course = connection.execute(
                text("SELECT name FROM courses WHERE id = :id"), {"id": course_id}
            ).scalar_one()
            indexed_content = connection.execute(
                text("SELECT content FROM document_fts")
            ).scalar_one()

        assert version == SCHEMA_VERSION
        assert saved_course == "Legacy Course"
        assert indexed_content == "Legacy indexed text"
    finally:
        engine.dispose()


def test_incompatible_unversioned_schema_is_not_stamped(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'incompatible.db'}")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE courses (id INTEGER PRIMARY KEY, name TEXT)")

    try:
        with pytest.raises(RuntimeError, match="No migration was applied"):
            migrate_schema(engine)

        with engine.connect() as connection:
            version = connection.exec_driver_sql("PRAGMA user_version").scalar_one()
            tables = set(
                connection.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).scalars()
            )

        assert version == 0
        assert tables == {"courses"}
    finally:
        engine.dispose()