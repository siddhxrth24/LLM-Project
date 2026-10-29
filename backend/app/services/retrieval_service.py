from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.logging_config import logger
from app.services.embedding_service import get_embedding_service
from app.services.keyword_service import search_keyword


def reciprocal_rank_fusion(
    dense_results: list[dict[str, Any]],
    keyword_results: list[dict[str, Any]],
    k: int = 60,
) -> list[dict[str, Any]]:
    """
    Combine dense semantic results and sparse keyword results using Reciprocal Rank Fusion (RRF).

    Formula: RRF_score(d) = sum_{m in models} 1 / (k + rank_m(d))

    Args:
        dense_results: Ranked list from vector search
        keyword_results: Ranked list from FTS5 keyword search
        k: Smoothing constant (default 60)

    Returns:
        Consolidated list of documents ordered by combined RRF score descending.
    """
    scores: dict[int, float] = {}
    doc_map: dict[int, dict[str, Any]] = {}

    # Process dense results
    for rank, item in enumerate(dense_results, start=1):
        cid = item.get("chunk_id")
        if not cid:
            continue
        scores[cid] = scores.get(cid, 0.0) + (1.0 / (k + rank))
        if cid not in doc_map:
            doc_map[cid] = dict(item)

    # Process keyword results
    for rank, item in enumerate(keyword_results, start=1):
        cid = item.get("chunk_id")
        if not cid:
            continue
        scores[cid] = scores.get(cid, 0.0) + (1.0 / (k + rank))
        if cid not in doc_map:
            doc_map[cid] = dict(item)

    # Sort candidates by combined score
    sorted_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)

    fused_results: list[dict[str, Any]] = []
    for cid in sorted_ids:
        entry = dict(doc_map[cid])
        entry["rrf_score"] = scores[cid]
        fused_results.append(entry)

    return fused_results


def hybrid_search(
    db: Session,
    query: str,
    course_id: int,
    unit_id: Optional[int] = None,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """
    Perform hybrid retrieval combining dense vector search and FTS5 keyword search.
    Falls back gracefully if vector embedding model is not yet loaded.
    """
    if not query or not query.strip():
        return []

    # 1. Keyword search via SQLite FTS5
    keyword_results: list[dict[str, Any]] = []
    try:
        keyword_results = search_keyword(
            db=db,
            query=query,
            course_id=course_id,
            unit_id=unit_id,
            top_k=top_k * 2,
        )
    except Exception as exc:
        logger.warning(f"Keyword search error in hybrid_search: {exc}")

    # 2. Dense semantic search via ChromaDB
    dense_results: list[dict[str, Any]] = []
    try:
        embedding_svc = get_embedding_service()
        dense_results = embedding_svc.search_dense(
            query=query,
            course_id=course_id,
            unit_id=unit_id,
            top_k=top_k * 2,
        )
    except Exception as exc:
        logger.warning(f"Dense vector search error in hybrid_search: {exc}")

    # 3. Fuse results if both or either are available
    if dense_results and keyword_results:
        fused = reciprocal_rank_fusion(dense_results, keyword_results)
        return fused[:top_k]
    elif dense_results:
        return dense_results[:top_k]
    elif keyword_results:
        return keyword_results[:top_k]
    else:
        return []


def format_context(results: list[dict[str, Any]]) -> str:
    """
    Format retrieved search chunks into a cited context string for LLM prompting.
    """
    if not results:
        return "No reference course materials found."

    context_blocks: list[str] = []
    for idx, item in enumerate(results, start=1):
        source = item.get("source_filename") or "Unknown Document"
        page = item.get("page_number")
        slide = item.get("slide_number")

        location = ""
        if page:
            location = f", Page {page}"
        elif slide:
            location = f", Slide {slide}"

        header = f"[Reference {idx} | Source: {source}{location}]"
        content = item.get("content", "").strip()
        context_blocks.append(f"{header}\n{content}")

    return "\n\n---\n\n".join(context_blocks)
