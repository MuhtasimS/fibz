from __future__ import annotations
from typing import List, Tuple
import os, mimetypes, tempfile

from vertexai.generative_models import Part
from fibz_bot.utils.http import download_file
from fibz_bot.storage.gcs import upload_bytes  # optional; harmless if GCS not configured


def _detect_mime(attachment, filename: str) -> str:
    """Prefer Discord's content_type; fall back to filename-based guess."""
    ct = getattr(attachment, "content_type", None) or ""
    if ct:
        return ct
    guess, _ = mimetypes.guess_type(filename)
    return guess or "application/octet-stream"


def make_parts_from_attachments(attachments: list) -> tuple[list[Part], list[str], list[dict]]:
    parts: list[Part] = []
    paths: list[str] = []
    metas: list[dict] = []

    for a in attachments:
        url = a.url
        name = a.filename or "file"
        mime = _detect_mime(a, name)
        ext = os.path.splitext(name)[1] or ".bin"

        # Save to a temp file
        fd, path = tempfile.mkstemp(prefix="fibz_", suffix=ext)
        os.close(fd)
        saved = download_file(url, path)
        if not saved:
            continue

        paths.append(saved)
        meta = {"filename": name, "mime": mime}

        try:
            with open(saved, "rb") as f:
                data = f.read()

            # Optional: upload to GCS for persistence / sharing
            try:
                gcs_uri = upload_bytes(
                    f"discord/{name}", data, content_type=mime
                )
                if gcs_uri:
                    meta["gcs_uri"] = gcs_uri
            except Exception:
                # GCS not configured or failed — ignore silently
                pass

            # Build a multimodal Part for Gemini
            # Use from_data for ALL binary media types (image/audio/video)
            if mime.startswith(("image/", "audio/", "video/")):
                parts.append(Part.from_data(mime_type=mime, data=data))
            else:
                # Non-media attachments: include a textual note so the model knows it's attached
                parts.append(Part.from_text(f"[Attachment: {name} ({mime}) attached]"))

        except Exception:
            # If anything goes wrong, still add a textual placeholder
            parts.append(Part.from_text(f"[Attachment: {name} attached but could not be read]"))

        metas.append(meta)

    return parts, paths, metas


def cleanup_temp(paths: list[str]):
    for p in paths:
        try:
            os.remove(p)
        except Exception:
            pass
