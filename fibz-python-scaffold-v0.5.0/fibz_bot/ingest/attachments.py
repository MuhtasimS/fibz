from __future__ import annotations
from typing import List, Tuple
import os, mimetypes, tempfile
from fibz_bot.utils.http import download_file
from fibz_bot.storage.gcs import upload_bytes
from vertexai.generative_models import Part

def make_parts_from_attachments(attachments: list) -> tuple[list[Part], list[str], list[dict]]:
    parts: list[Part] = []
    paths: list[str] = []
    metas: list[dict] = []
    for a in attachments:
        url = a.url
        name = a.filename or "file"
        mime, _ = mimetypes.guess_type(name)
        ext = os.path.splitext(name)[1] or ".bin"
        fd, path = tempfile.mkstemp(prefix="fibz_", suffix=ext)
        os.close(fd)
        saved = download_file(url, path)
        if not saved:
            continue
        paths.append(saved)
        meta = {"filename": name, "mime": mime or "application/octet-stream"}
        try:
            with open(saved, "rb") as f:
                data = f.read()
            # optional GCS upload
            gcs_uri = upload_bytes(f"discord/{name}", data, content_type=mime or "application/octet-stream")
            if gcs_uri:
                meta["gcs_uri"] = gcs_uri
            if mime and mime.startswith("image/"):
                parts.append(Part.from_image(data))
            elif mime and (mime.startswith("audio/") or mime.startswith("video/")):
                parts.append(Part.from_mime_type(mime_type=mime, data=data))
            else:
                parts.append(Part.from_text(f"[Attachment: {name} ({mime or 'application/octet-stream'}) attached]"))
        except Exception:
            parts.append(Part.from_text(f"[Attachment: {name} attached but could not be read]"))
        metas.append(meta)
    return parts, paths, metas

def cleanup_temp(paths: list[str]):
    for p in paths:
        try:
            os.remove(p)
        except Exception:
            pass
