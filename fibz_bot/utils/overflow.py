from __future__ import annotations

from pathlib import Path
from uuid import uuid4

MAX_VISIBLE_CHARS = 1800
SUMMARY_CHARS = 400


def prepare_overflow_text(
    text: str,
    *,
    base_dir: Path = Path("tmp/overflow"),
) -> tuple[str, Path | None]:
    """Return (display_text, attachment_path)."""

    if len(text) <= MAX_VISIBLE_CHARS:
        return text, None

    base_dir.mkdir(parents=True, exist_ok=True)
    file_id = uuid4().hex
    path = base_dir / f"fibz-overflow-{file_id}.txt"
    path.write_text(text, encoding="utf-8")

    summary = text[:SUMMARY_CHARS]
    if len(text) > SUMMARY_CHARS:
        summary += "…"
    summary = summary.strip()
    if not summary:
        summary = "Response saved to attachment."

    display = f"{summary}\n\nFull response attached as fibz-overflow-{file_id}.txt"
    return display[:MAX_VISIBLE_CHARS], path


__all__ = ["prepare_overflow_text", "MAX_VISIBLE_CHARS"]
