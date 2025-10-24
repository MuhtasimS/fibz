from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar, cast

from fibz_bot.utils.logging import get_logger

try:  # pragma: no cover - optional dependency
    from google.api_core import exceptions as google_exceptions  # type: ignore
except Exception:  # pragma: no cover - google libs optional in tests
    google_exceptions = None  # type: ignore

try:  # pragma: no cover - optional dependency
    import requests  # type: ignore[import-untyped]
    from requests import exceptions as requests_exceptions  # type: ignore[import-untyped]
except Exception:  # pragma: no cover - requests always available but keep safe
    requests = None  # type: ignore[assignment]
    requests_exceptions = None  # type: ignore[assignment]

T = TypeVar("T")

log = get_logger(__name__)

_RETRYABLE_GOOGLE_EXC_TYPES: tuple[type[BaseException], ...]
if google_exceptions is not None:  # pragma: no branch - evaluated once
    _RETRYABLE_GOOGLE_EXC_TYPES = (
        google_exceptions.ResourceExhausted,
        google_exceptions.ServiceUnavailable,
        google_exceptions.InternalServerError,
        google_exceptions.DeadlineExceeded,
        google_exceptions.Aborted,
    )
else:
    _RETRYABLE_GOOGLE_EXC_TYPES = tuple()

if requests_exceptions is not None:
    _RETRYABLE_REQUESTS_EXC_TYPES = cast(
        tuple[type[BaseException], ...],
        (
            requests_exceptions.Timeout,
            requests_exceptions.ConnectionError,
        ),
    )
else:
    _RETRYABLE_REQUESTS_EXC_TYPES = tuple()


def _status_from_exception(exc: BaseException) -> int | None:
    response = getattr(exc, "response", None)
    if response is not None:
        return getattr(response, "status_code", None)
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return code
    # google exceptions sometimes expose grpc.StatusCode
    name = getattr(code, "name", None)
    if isinstance(name, str):
        mapping = {
            "RESOURCE_EXHAUSTED": 429,
            "UNAVAILABLE": 503,
            "INTERNAL": 500,
            "DEADLINE_EXCEEDED": 504,
            "ABORTED": 409,
        }
        return mapping.get(name)
    return None


def is_retryable_exception(exc: BaseException) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    if _RETRYABLE_GOOGLE_EXC_TYPES and isinstance(exc, _RETRYABLE_GOOGLE_EXC_TYPES):
        return True
    if _RETRYABLE_REQUESTS_EXC_TYPES and isinstance(exc, _RETRYABLE_REQUESTS_EXC_TYPES):
        return True
    if requests_exceptions is not None and isinstance(exc, requests_exceptions.HTTPError):
        status = _status_from_exception(exc)
        if status == 429 or (status is not None and 500 <= status < 600):
            return True
        return False
    status = _status_from_exception(exc)
    if status == 429 or (status is not None and 500 <= status < 600):
        return True
    return False


def retry(
    func: Callable[[], T],
    *,
    max_attempts: int = 5,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    operation: str | None = None,
) -> T:
    """Run ``func`` with exponential backoff + full jitter."""

    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    attempt = 0
    while True:
        try:
            return func()
        except Exception as exc:  # pragma: no cover - exercised via tests
            attempt += 1
            retryable = is_retryable_exception(exc)
            if attempt >= max_attempts or not retryable:
                raise
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            sleep_for = random.uniform(0, delay)
            log.warning(
                "retrying_operation",
                extra={
                    "extra_fields": {
                        "operation": operation or getattr(func, "__name__", "call"),
                        "attempt": attempt,
                        "delay": round(sleep_for, 3),
                        "error": exc.__class__.__name__,
                    }
                },
            )
            time.sleep(sleep_for)


__all__ = ["retry", "is_retryable_exception"]
