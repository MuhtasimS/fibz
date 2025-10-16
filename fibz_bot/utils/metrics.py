from __future__ import annotations
from typing import Dict
import time
from threading import RLock

class Metrics:
    def __init__(self) -> None:
        self.started = time.time()
        self._counters: Dict[str, int] = {}
        self._lock = RLock()

    def inc(self, key: str, n: int = 1) -> None:
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + n

    def snapshot(self) -> Dict[str, object]:
        with self._lock:
            data = dict(self._counters)
        data["uptime_seconds"] = int(time.time() - self.started)
        return data

metrics = Metrics()

def record_model_choice(tier: str) -> None:
    metrics.inc(f"model_choice.{tier}", 1)

def record_tool_call(name: str) -> None:
    metrics.inc(f"tool.{name}", 1)

def record_command(name: str) -> None:
    metrics.inc(f"cmd.{name}", 1)
