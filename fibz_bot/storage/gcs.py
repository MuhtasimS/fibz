from __future__ import annotations

from fibz_bot.config import settings
from fibz_bot.utils.backoff import retry
from fibz_bot.utils.logging import get_logger

log = get_logger(__name__)

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


def upload_bytes(path_in_bucket: str, data: bytes, content_type: str | None = None) -> str | None:
    client, bucket = _client()
    if not bucket:
        return None
    blob = bucket.blob(path_in_bucket)
    try:
        retry(
            lambda: blob.upload_from_string(
                data, content_type=content_type or "application/octet-stream"
            ),
            operation="gcs_upload",
        )
        return f"gs://{settings.GCS_BUCKET}/{path_in_bucket}"
    except Exception as exc:  # pragma: no cover - relies on GCS libraries
        log.error(
            "gcs_upload_failed",
            extra={
                "extra_fields": {
                    "path": path_in_bucket,
                    "error": exc.__class__.__name__,
                }
            },
        )
        return None


def sign_url(path_in_bucket: str) -> str | None:
    client, bucket = _client()
    if not bucket or not settings.GCS_SIGN_URLS:
        return None
    blob = bucket.blob(path_in_bucket)
    try:
        return retry(
            lambda: blob.generate_signed_url(
                expiration=settings.GCS_SIGN_URL_EXPIRY_SECONDS, method="GET"
            ),
            operation="gcs_sign",
        )
    except Exception as exc:  # pragma: no cover - depends on GCS client
        log.error(
            "gcs_sign_failed",
            extra={
                "extra_fields": {
                    "path": path_in_bucket,
                    "error": exc.__class__.__name__,
                }
            },
        )
        return None
