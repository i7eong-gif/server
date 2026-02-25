import time
from typing import Any, Dict

class TTLCache:
    def __init__(self, ttl_seconds: int):
        self.ttl = ttl_seconds
        self.store: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str):
        item = self.store.get(key)
        if not item:
            return None

        if time.time() - item["ts"] > self.ttl:
            del self.store[key]
            return None

        return item["value"]

    def set(self, key: str, value: Any):
        self.store[key] = {
            "value": value,
            "ts": time.time(),
        }
