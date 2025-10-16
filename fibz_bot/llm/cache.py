from __future__ import annotations
from typing import Tuple, Dict
import time
from hashlib import sha256

class PromptCache:
    def __init__(self, max_items: int = 256, ttl_sec: int = 3600):
        self.max = max_items
        self.ttl = ttl_sec
        self._store: Dict[str, Tuple[float,str]] = {}

    def _key(self, core: str, user: str, server: str, policy: str) -> str:
        h = sha256((core + "|" + user + "|" + server + "|" + policy).encode("utf-8")).hexdigest()
        return h

    def get(self, core: str, user: str, server: str, policy: str) -> str | None:
        key = self._key(core, user, server, policy)
        item = self._store.get(key)
        if not item: return None
        ts, val = item
        if time.time() - ts > self.ttl:
            self._store.pop(key, None)
            return None
        return val

    def set(self, core: str, user: str, server: str, policy: str, prompt: str) -> None:
        if len(self._store) >= self.max:
            oldest = sorted(self._store.items(), key=lambda kv: kv[1][0])[0][0]
            self._store.pop(oldest, None)
        key = self._key(core, user, server, policy)
        self._store[key] = (time.time(), prompt)
