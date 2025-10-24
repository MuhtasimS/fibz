from __future__ import annotations

from pathlib import Path

from fibz_bot.memory.store import MemoryStore
from fibz_bot.config import settings


class DummyRouter:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[float(i + 1)] for i, _ in enumerate(texts)]


def test_entity_roundtrip(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(settings, "CHROMA_PATH", str(tmp_path / "chroma"))
    store = MemoryStore(DummyRouter())
    store.upsert_entity(
        "user:123",
        "- enjoys chess",
        {"kind": "user", "display_name": "Alice", "tags": ["summary"]},
    )
    entity = store.get_entity("user:123")
    assert entity is not None
    assert entity["document"].strip().startswith("-")
    meta = entity["metadata"]
    assert meta["entity_id"] == "user:123"
    assert "entity" in meta["tags"]
    assert "updated_at" in meta
