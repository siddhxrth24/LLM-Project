from pathlib import Path
from typing import Any, Optional

from app.core.config import settings
from app.core.logging_config import logger


class EmbeddingService:
    """Manages text embedding generation and vector storage via ChromaDB."""

    _instance: Optional["EmbeddingService"] = None

    def __init__(self) -> None:
        self.model: Any = None
        self._chroma_client: Any = None
        self._collection: Any = None
        self.collection_name = "semestrack_chunks"
        self._init_chroma()

    @classmethod
    def get_instance(cls) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _init_chroma(self) -> None:
        """Initialize ChromaDB client with persistent local storage."""
        try:
            import chromadb

            chroma_dir = settings.resolved_chroma_dir
            chroma_dir.mkdir(parents=True, exist_ok=True)
            self._chroma_client = chromadb.PersistentClient(path=str(chroma_dir))
            self._collection = self._chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(f"ChromaDB initialized at {chroma_dir} with collection '{self.collection_name}'")
        except Exception as exc:
            logger.error(f"Failed to initialize ChromaDB: {exc}")
            self._chroma_client = None
            self._collection = None

    def is_loaded(self) -> bool:
        return self.model is not None

    def is_vector_store_ready(self) -> bool:
        return self._collection is not None

    def load_model(self) -> bool:
        """Load sentence-transformers model from local disk path or model ID."""
        if self.model is not None:
            return True

        local_path = settings.resolved_embedding_model_path
        try:
            has_local_model = local_path.is_dir() and any(local_path.iterdir())
        except OSError:
            has_local_model = False
        if not has_local_model:
            logger.warning(f"Embedding model files are unavailable locally at {local_path}.")
            return False

        logger.info(f"Attempting to load embedding model from '{local_path}' (CPU-only)...")
        try:
            from sentence_transformers import SentenceTransformer

            # Offline CPU loading
            self.model = SentenceTransformer(
                str(local_path), device="cpu", local_files_only=True
            )
            logger.info("SentenceTransformer embedding model successfully loaded.")
            return True
        except Exception as exc:
            logger.warning(
                f"Embedding model could not be loaded from '{local_path}': {exc}. "
                f"For offline use, please download the model to {local_path}."
            )
            self.model = None
            return False

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Compute embedding vectors for a list of text strings."""
        if not texts:
            return []

        if self.model is None:
            loaded = self.load_model()
            if not loaded or self.model is None:
                raise RuntimeError(
                    f"Embedding model is not loaded. Model not found locally at "
                    f"{settings.resolved_embedding_model_path}. Please download it for offline use."
                )

        embeddings = self.model.encode(
            texts,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

    def store_chunks(
        self,
        chunks: list[dict[str, Any]],
        course_id: int,
        unit_id: int,
        document_id: int,
    ) -> list[str]:
        """
        Compute embeddings and save document chunks to ChromaDB.

        Args:
            chunks: List of chunk dictionaries containing 'content', 'chunk_index', etc.
            course_id: Course ID
            unit_id: Unit ID
            document_id: Document ID

        Returns:
            List of generated Chroma embedding IDs.
        """
        if not chunks:
            return []

        if self._collection is None:
            self._init_chroma()
            if self._collection is None:
                raise RuntimeError("ChromaDB collection is unavailable.")

        texts = [c["content"] for c in chunks]
        embeddings = self.embed_texts(texts)

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for c, emb in zip(chunks, embeddings):
            c_idx = c.get("chunk_index", 0)
            chunk_db_id = c.get("id")
            chroma_id = f"doc_{document_id}_chunk_{c_idx}"
            ids.append(chroma_id)
            documents.append(c["content"])

            # Metadata values in Chroma must be str, int, float, or bool
            meta: dict[str, Any] = {
                "course_id": int(course_id),
                "unit_id": int(unit_id),
                "document_id": int(document_id),
                "chunk_index": int(c_idx),
                "chunk_id": int(chunk_db_id) if chunk_db_id is not None else 0,
                "source_filename": str(c.get("source_filename", "")),
                "page_number": int(c.get("page_number") or 0),
                "slide_number": int(c.get("slide_number") or 0),
            }
            metadatas.append(meta)

        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info(f"Stored {len(ids)} chunks in ChromaDB for document {document_id}")
        return ids

    def delete_chunks(self, document_id: int) -> bool:
        """Remove all vectors associated with a document ID from ChromaDB."""
        if self._collection is None:
            return True
        try:
            self._collection.delete(where={"document_id": int(document_id)})
            logger.info(f"Deleted ChromaDB vectors for document {document_id}")
            return True
        except Exception as exc:
            logger.error(f"Error deleting Chroma chunks for document {document_id}: {exc}")
            return False

    def search_dense(
        self,
        query: str,
        course_id: Optional[int] = None,
        unit_id: Optional[int] = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Execute dense vector similarity search.

        Returns list of dicts with:
        {'chunk_id': int, 'content': str, 'score': float, 'metadata': dict, 'source_filename': str}
        """
        if self._collection is None:
            self._init_chroma()
            if self._collection is None:
                return []

        if not self.is_loaded():
            loaded = self.load_model()
            if not loaded:
                logger.warning("Dense search skipped: embedding model not loaded.")
                return []

        query_embedding = self.embed_texts([query])[0]

        # Construct where filter
        where_filter: Optional[dict[str, Any]] = None
        if course_id is not None and unit_id is not None:
            where_filter = {
                "$and": [
                    {"course_id": int(course_id)},
                    {"unit_id": int(unit_id)},
                ]
            }
        elif course_id is not None:
            where_filter = {"course_id": int(course_id)}
        elif unit_id is not None:
            where_filter = {"unit_id": int(unit_id)}

        try:
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            logger.error(f"Chroma dense query failed: {exc}")
            return []

        output: list[dict[str, Any]] = []
        if not results or not results.get("documents"):
            return output

        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(documents, metadatas, distances):
            # Cosine distance in Chroma ranges from 0 (identical) to 2 (opposite)
            similarity = max(0.0, 1.0 - (dist / 2.0))
            output.append(
                {
                    "chunk_id": int(meta.get("chunk_id", 0)),
                    "content": doc,
                    "score": float(similarity),
                    "metadata": meta,
                    "source_filename": str(meta.get("source_filename", "")),
                    "page_number": meta.get("page_number"),
                    "slide_number": meta.get("slide_number"),
                }
            )

        return output

    def get_status(self) -> dict[str, Any]:
        """Return diagnostic status of embedding model and vector database."""
        count = 0
        if self._collection is not None:
            try:
                count = self._collection.count()
            except Exception:
                count = 0

        return {
            "embedding_loaded": self.is_loaded(),
            "embedding_model_id": settings.EMBEDDING_MODEL_ID,
            "embedding_model_path": str(settings.resolved_embedding_model_path),
            "embedding_device": "cpu",
            "chroma_dir": str(settings.resolved_chroma_dir),
            "collection_size": count,
        }


def get_embedding_service() -> EmbeddingService:
    return EmbeddingService.get_instance()
