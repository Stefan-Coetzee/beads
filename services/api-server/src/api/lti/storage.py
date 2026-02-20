"""
Redis-backed launch data storage for PyLTI1p3.

Stores nonces, state, and launch data in Redis with TTL expiry.
This avoids third-party cookie issues in iframe contexts.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from pylti1p3.launch_data_storage.base import LaunchDataStorage

logger = logging.getLogger(__name__)


class RedisLaunchDataStorage(LaunchDataStorage):
    """Stores LTI launch data in Redis with automatic expiry."""

    _PREFIX = "lti1p3:"
    _DEFAULT_TTL = 7200  # 2 hours

    def __init__(self, redis_client):
        super().__init__()
        self._redis = redis_client

    @classmethod
    def from_url(cls, redis_url: str = "redis://localhost:6379/0") -> "RedisLaunchDataStorage":
        """Create storage from Redis URL using sync client (PyLTI1p3 is sync)."""
        import redis as sync_redis

        client = sync_redis.Redis.from_url(redis_url, decode_responses=True)
        return cls(client)

    def can_set_keys_expiration(self) -> bool:
        return True

    def _prepare_key(self, key: str) -> str:
        return f"{self._PREFIX}{key}"

    def get_value(self, key: str) -> Optional[dict]:
        prepared_key = self._prepare_key(key)
        value = self._redis.get(prepared_key)
        if value:
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    def set_value(self, key: str, value: Any, exp: Optional[int] = None) -> None:
        prepared_key = self._prepare_key(key)
        serialized = json.dumps(value)
        ttl = exp or self._DEFAULT_TTL
        self._redis.setex(prepared_key, ttl, serialized)

    def check_value(self, key: str) -> bool:
        prepared_key = self._prepare_key(key)
        return bool(self._redis.exists(prepared_key))
