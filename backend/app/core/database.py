from collections.abc import Generator
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings
from app.core.logging_config import logger


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 base model."""
    pass


# SQLite-specific connect args
connect_args: dict[str, Any] = {}
resolved_url = settings.resolved_database_url
if resolved_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    resolved_url,
    connect_args=connect_args,
    echo=False,
    future=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database directories, tables, and FTS5 virtual table."""
    logger.info("Initializing database...")

    # Ensure data, upload, and chroma directories exist
    db_url = settings.resolved_database_url
    if db_url.startswith("sqlite:///") and not db_url.startswith("sqlite:///:memory:"):
        db_path = Path(db_url.replace("sqlite:///", ""))
        db_path.parent.mkdir(parents=True, exist_ok=True)

    settings.resolved_upload_dir.mkdir(parents=True, exist_ok=True)
    settings.resolved_chroma_dir.mkdir(parents=True, exist_ok=True)

    # Import models here so metadata knows about them
    import app.models.models  # noqa: F401

    # Create standard tables
    Base.metadata.create_all(bind=engine)
    logger.info("Standard tables created successfully.")

    # Create FTS5 virtual table for keyword search
    try:
        with engine.begin() as conn:
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
            logger.info("FTS5 document_fts table verified/created.")
    except Exception as exc:
        logger.error(f"Failed to create FTS5 virtual table: {exc}")
        raise
