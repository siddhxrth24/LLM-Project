import os
import sys
from types import ModuleType, SimpleNamespace

from app.services.embedding_service import EmbeddingService


def test_chroma_initialization_disables_telemetry(monkeypatch, tmp_path) -> None:
    collection = object()

    class FakeClient:
        def get_or_create_collection(self, **_):
            return collection

    chromadb = ModuleType("chromadb")
    chromadb.PersistentClient = lambda **_: FakeClient()
    monkeypatch.setitem(sys.modules, "chromadb", chromadb)
    monkeypatch.setattr(
        "app.services.embedding_service.settings",
        SimpleNamespace(resolved_chroma_dir=tmp_path),
    )
    monkeypatch.setenv("ANONYMIZED_TELEMETRY", "True")

    service = EmbeddingService.__new__(EmbeddingService)
    service._chroma_client = None
    service._collection = None
    service.collection_name = "semestrack_chunks"
    service._init_chroma()

    assert os.environ["ANONYMIZED_TELEMETRY"] == "False"
    assert service._collection is collection