from __future__ import annotations
from typing import Optional
from fibz_bot.config import settings

try:
    from google.cloud import storage
except Exception:
    storage = None

def _client():
    if storage is None or not settings.GCS_BUCKET:
        return None, None
    client = storage.Client(project=settings.VERTEX_PROJECT_ID)
    bucket = client.bucket(settings.GCS_BUCKET)
    return client, bucket

def upload_bytes(path_in_bucket: str, data: bytes, content_type: str | None = None) -> Optional[str]:
    client, bucket = _client()
    if not bucket:
        return None
    blob = bucket.blob(path_in_bucket)
    blob.upload_from_string(data, content_type=content_type or "application/octet-stream")
    return f"gs://{settings.GCS_BUCKET}/{path_in_bucket}"

def sign_url(path_in_bucket: str) -> Optional[str]:
    client, bucket = _client()
    if not bucket or not settings.GCS_SIGN_URLS:
        return None
    blob = bucket.blob(path_in_bucket)
    try:
        url = blob.generate_signed_url(expiration=settings.GCS_SIGN_URL_EXPIRY_SECONDS, method="GET")
        return url
    except Exception:
        return None
