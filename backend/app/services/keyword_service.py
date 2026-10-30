import re
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logging_config import logger
from app.models.models import Chunk


def sanitize_fts_query(query: str) -> str:
    """
    Sanitize raw query string into safe FTS5 query terms.
    Escapes quotes, removes control characters, and joins terms with OR.
    """
    # Keep alphanumeric tokens
    tokens = re.findall(r"\b[A-Za-z0-9_]+\b", query)
    if not tokens:
        return ""
    # Filter short stop-words or 1-char tokens
    valid_tokens = [t for t in tokens if len(t) > 1 or t.isdigit()]
    if not valid_tokens:
        valid_tokens = tokens

    # Query terms wrapped in quotes to avoid syntax collisions
    terms = [f'"{token}"' for token in valid_tokens]
    return " OR ".join(terms)


def index_chunk(
    db: Session,
    chunk_id: int,
    course_id: int,
    unit_id: int,
    source_filename: str,
    page_number: Optional[int],
    content: str,
) -> None:
    """Insert a single chunk into SQLite FTS5 table."""
    try:
        query = text(
            """
            INSERT INTO document_fts (chunk_id, course_id, unit_id, source_filename, page_number, content)
            VALUES (:chunk_id, :course_id, :unit_id, :source_filename, :page_number, :content)
            """
        )
        db.execute(
            query,
            {
                "chunk_id": str(chunk_id),
                "course_id": str(course_id),
                "unit_id": str(unit_id),
                "source_filename": source_filename,
                "page_number": str(page_number or 0),
                "content": content,
            },
        )
    except Exception as exc:
        logger.error(f"Failed to index chunk {chunk_id} in FTS5: {exc}")
        raise


def index_chunks_batch(db: Session, chunks_data: list[dict[str, Any]]) -> None:
    """Batch insert multiple chunks into FTS5 table."""
    if not chunks_data:
        return

    try:
        query = text(
            """
            INSERT INTO document_fts (chunk_id, course_id, unit_id, source_filename, page_number, content)
            VALUES (:chunk_id, :course_id, :unit_id, :source_filename, :page_number, :content)
            """
        )
        params = [
            {
                "chunk_id": str(c["id"]),
                "course_id": str(c["course_id"]),
                "unit_id": str(c["unit_id"]),
                "source_filename": str(c.get("source_filename", "")),
                "page_number": str(c.get("page_number") or c.get("slide_number") or 0),
                "content": c["content"],
            }
            for c in chunks_data
        ]
        db.execute(query, params)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to batch index {len(chunks_data)} chunks in FTS5: {exc}")
        raise


def delete_chunks(db: Session, document_id: int) -> None:
    """Remove all FTS5 index entries associated with a document ID."""
    try:
        # Look up chunk ids belonging to document
            db.execute(
                text(
                    """
                    DELETE FROM document_fts
                    WHERE chunk_id IN (
                        SELECT CAST(id AS TEXT) FROM chunks WHERE document_id = :document_id
                    )
                    OR chunk_id NOT IN (SELECT CAST(id AS TEXT) FROM chunks)
                    """
                ),
                {"document_id": document_id},
            )
            logger.info(f"Deleted FTS5 entries for document {document_id}")
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to delete FTS5 chunks for document {document_id}: {exc}")


def search_keyword(
    db: Session,
    query: str,
    course_id: Optional[int] = None,
    unit_id: Optional[int] = None,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """
    Search FTS5 full-text table and return ranked results.

    Returns:
        List of dicts:
        {'chunk_id': int, 'content': str, 'score': float, 'source_filename': str, 'page_number': int | None}
    """
    fts_query = sanitize_fts_query(query)
    if not fts_query:
        return []

    # Build SQL dynamically with conditions
    sql_parts = [
        "SELECT chunk_id, course_id, unit_id, source_filename, page_number, content, rank",
        "FROM document_fts",
        "WHERE document_fts MATCH :match_query",
    ]
    params: dict[str, Any] = {"match_query": fts_query, "limit": top_k}

    if course_id is not None:
        sql_parts.append("AND course_id = :course_id")
        params["course_id"] = str(course_id)

    if unit_id is not None:
        sql_parts.append("AND unit_id = :unit_id")
        params["unit_id"] = str(unit_id)

    sql_parts.append("ORDER BY rank LIMIT :limit")
    final_sql = " ".join(sql_parts)

    try:
        results = db.execute(text(final_sql), params).fetchall()
    except Exception as exc:
        logger.warning(f"FTS5 keyword query failed: {exc}")
        return []

    output: list[dict[str, Any]] = []
    for row in results:
        # SQLite FTS5 rank: lower is better (usually negative BM25 score)
        # Normalize to positive score: 1 / (1 + abs(rank))
        raw_rank = float(row[6]) if row[6] is not None else 0.0
        score = 1.0 / (1.0 + abs(raw_rank))
        pg = int(row[4]) if row[4] and str(row[4]).isdigit() and int(row[4]) > 0 else None

        output.append(
            {
                "chunk_id": int(row[0]),
                "course_id": int(row[1]),
                "unit_id": int(row[2]),
                "source_filename": str(row[3]),
                "page_number": pg,
                "content": str(row[5]),
                "score": float(score),
            }
        )

    return output
