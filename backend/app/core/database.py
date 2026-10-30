from collections.abc import Generator
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Connection, Engine
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

SCHEMA_VERSION = 1
FTS_TABLE_SQL = """
    CREATE VIRTUAL TABLE document_fts USING fts5(
        chunk_id UNINDEXED,
        course_id UNINDEXED,
        unit_id UNINDEXED,
        source_filename UNINDEXED,
        page_number UNINDEXED,
        content,
        tokenize='porter unicode61'
    )
"""


def _validate_existing_columns(connection: Connection, existing_tables: set[str]) -> None:
    inspector = inspect(connection)
    incompatible: list[str] = []

    for table_name in existing_tables & set(Base.metadata.tables):
        actual_columns = {column["name"] for column in inspector.get_columns(table_name)}
        expected_columns = {column.name for column in Base.metadata.tables[table_name].columns}
        missing_columns = expected_columns - actual_columns
        if missing_columns:
            incompatible.append(
                f"{table_name} is missing columns: {', '.join(sorted(missing_columns))}"
            )

    if incompatible:
        details = "; ".join(incompatible)
        raise RuntimeError(
            "The existing database schema is incompatible with this version. "
            f"No migration was applied. {details}"
        )


def _validate_model_schema(connection: Connection) -> None:
    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())
    missing_tables = set(Base.metadata.tables) - existing_tables
    if missing_tables:
        raise RuntimeError(
            "Database migration did not create required tables: "
            + ", ".join(sorted(missing_tables))
        )
    _validate_existing_columns(connection, existing_tables)


def _ensure_fts_table(connection: Connection) -> None:
    table = connection.execute(
        text("SELECT type, sql FROM sqlite_master WHERE name = 'document_fts'")
    ).one_or_none()
    if table is None:
        connection.exec_driver_sql(FTS_TABLE_SQL)
        connection.execute(
            text(
                """
                INSERT INTO document_fts (
                    chunk_id, course_id, unit_id, source_filename, page_number, content
                )
                SELECT CAST(id AS TEXT), CAST(course_id AS TEXT), CAST(unit_id AS TEXT),
                       source_filename, CAST(COALESCE(page_number, slide_number, 0) AS TEXT),
                       content
                FROM chunks
                """
            )
        )
        return

    expected_columns = {
        "chunk_id", "course_id", "unit_id", "source_filename", "page_number", "content"
    }
    actual_columns = {
        column[1] for column in connection.exec_driver_sql("PRAGMA table_info(document_fts)")
    }
    if (
        table[0] != "table"
        or "USING FTS5" not in (table[1] or "").upper()
        or not expected_columns.issubset(actual_columns)
    ):
        raise RuntimeError("The existing document_fts index has an incompatible schema.")


def migrate_schema(target_engine: Engine) -> None:
    """Apply the versioned SQLite schema baseline without replacing user data."""
    if target_engine.dialect.name != "sqlite":
        raise RuntimeError("Schema migrations currently support SQLite only.")

    # Import models so Base.metadata includes every application table.
    import app.models.models  # noqa: F401

    with target_engine.begin() as connection:
        current_version = int(connection.exec_driver_sql("PRAGMA user_version").scalar_one())
        if current_version > SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema version {current_version} is newer than supported "
                f"version {SCHEMA_VERSION}."
            )

        existing_tables = set(inspect(connection).get_table_names())
        if current_version == 0:
            # Validate existing application tables before any additive changes.
            _validate_existing_columns(connection, existing_tables)
            Base.metadata.create_all(bind=connection)
            _validate_model_schema(connection)
            _ensure_fts_table(connection)
            connection.exec_driver_sql(f"PRAGMA user_version = {SCHEMA_VERSION}")
        else:
            _validate_model_schema(connection)
            _ensure_fts_table(connection)


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

    migrate_schema(engine)
    logger.info(f"Database schema is at version {SCHEMA_VERSION}.")
