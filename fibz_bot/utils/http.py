from __future__ import annotations

from typing import Any

import requests  # type: ignore[import-untyped]

from fibz_bot.utils.backoff import retry
from fibz_bot.utils.logging import get_logger

log = get_logger(__name__)


def get_json(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 20,
) -> tuple[dict | None, str | None]:
    def _call() -> dict:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    try:
        data = retry(_call, operation="http_get_json")
        return data, None
    except Exception as exc:  # pragma: no cover - captured in tests
        log.error(
            "http_get_json_failed",
            extra={"extra_fields": {"operation": "http_get_json", "error": str(exc)[:200]}},
        )
        return None, str(exc)


def download_file(
    url: str,
    dest_path: str,
    headers: dict[str, str] | None = None,
    timeout: int = 60,
) -> str | None:
    def _call() -> str:
        with requests.get(url, stream=True, headers=headers, timeout=timeout) as r:
            r.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return dest_path

    try:
        return retry(_call, operation="http_download")
    except Exception as exc:  # pragma: no cover - captured in tests
        log.error(
            "http_download_failed",
            extra={"extra_fields": {"operation": "http_download", "error": str(exc)[:200]}},
        )
        return None
