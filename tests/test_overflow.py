from __future__ import annotations

from fibz_bot.utils.overflow import MAX_VISIBLE_CHARS, prepare_overflow_text


def test_prepare_overflow_short(tmp_path):
    display, path = prepare_overflow_text("hello", base_dir=tmp_path)
    assert display == "hello"
    assert path is None


def test_prepare_overflow_creates_attachment(tmp_path):
    text = "a" * (MAX_VISIBLE_CHARS + 50)
    display, path = prepare_overflow_text(text, base_dir=tmp_path)
    assert path is not None
    assert path.exists()
    assert len(display) <= MAX_VISIBLE_CHARS
    assert "Full response attached" in display
    assert path.read_text(encoding="utf-8") == text
