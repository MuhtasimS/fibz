from __future__ import annotations

import pytest
import requests

import fibz_bot.utils.backoff as backoff
from fibz_bot.utils.http import get_json


def test_retry_retries_on_http_error(monkeypatch):
    calls = []

    def _call():
        calls.append(True)
        if len(calls) < 3:
            response = requests.Response()
            response.status_code = 500
            raise requests.exceptions.HTTPError(response=response)
        return "ok"

    monkeypatch.setattr(backoff.random, "uniform", lambda *_: 0.0)
    sleeps: list[float] = []
    monkeypatch.setattr(backoff.time, "sleep", lambda s: sleeps.append(s))

    assert backoff.retry(_call, max_attempts=5) == "ok"
    assert len(calls) == 3
    assert sleeps == [0.0, 0.0]


def test_retry_non_retryable_exception(monkeypatch):
    response = requests.Response()
    response.status_code = 400

    def _call():
        raise requests.exceptions.HTTPError(response=response)

    monkeypatch.setattr(backoff.random, "uniform", lambda *_: 0.0)
    monkeypatch.setattr(backoff.time, "sleep", lambda _: None)

    with pytest.raises(requests.exceptions.HTTPError):
        backoff.retry(_call, max_attempts=5)


def test_get_json_uses_retries(monkeypatch):
    attempts = 0

    class FakeResp:
        def __init__(self, status_code: int, payload: dict[str, str]):
            self.status_code = status_code
            self._payload = payload

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise requests.exceptions.HTTPError(response=self)

        def json(self) -> dict[str, str]:
            return self._payload

    def fake_get(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return FakeResp(500, {})
        return FakeResp(200, {"ok": "yes"})

    monkeypatch.setattr(backoff.random, "uniform", lambda *_: 0.0)
    monkeypatch.setattr(backoff.time, "sleep", lambda _: None)
    monkeypatch.setattr("fibz_bot.utils.http.requests.get", fake_get)

    data, err = get_json("https://example.com")
    assert data == {"ok": "yes"}
    assert err is None
    assert attempts == 3
