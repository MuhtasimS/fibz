from __future__ import annotations

import asyncio
from pathlib import Path

from fibz_bot.config import settings
from fibz_bot.llm import revision
from fibz_bot.memory.store import MemoryStore


class DummyRouter:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.1 for _ in range(2)] for _ in texts]


def test_owner_updates_bot_entity(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(settings, "CHROMA_PATH", str(tmp_path / "chroma"))
    monkeypatch.setattr(settings, "ENTITY_REVISION_ENABLED", True)
    store = MemoryStore(DummyRouter())

    def fake_extract(_router, _payload):
        return {
            "facts": ["Fibz now supports entity summaries."],
            "targets": [{"entity_id": "bot:self", "kind": "bot", "display_name": "Fibz"}],
            "sensitive": [],
        }

    monkeypatch.setattr(revision, "extract_entities", fake_extract)

    asyncio.run(
        revision.run_entity_revision_pass(
            DummyRouter(),
            store,
            author_id="owner",
            author_display="Owner",
            guild_id="123",
            channel_id="456",
            message_text="We upgraded Fibz to support entity summaries.",
            answer_text=None,
            is_owner=True,
        )
    )

    entity = store.get_entity("bot:self")
    assert entity is not None
    assert "entity summaries" in entity["document"].lower()
    channels = entity["metadata"].get("channels", "")
    assert "456" in [c for c in channels.split(",") if c]
