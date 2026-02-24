"""Unit tests for RedisLaunchDataStorage."""

import json


class TestRedisLaunchDataStorage:
    def test_set_and_get_value(self, lti_storage):
        """set_value stores JSON, get_value deserializes it."""
        lti_storage.set_value("test-key", {"foo": "bar"}, exp=60)
        result = lti_storage.get_value("test-key")
        assert result == {"foo": "bar"}

    def test_get_value_missing_key_returns_none(self, lti_storage):
        """get_value returns None for non-existent keys."""
        assert lti_storage.get_value("nonexistent") is None

    def test_check_value_exists(self, lti_storage):
        """check_value returns True for existing keys."""
        lti_storage.set_value("exists", {"v": 1}, exp=60)
        assert lti_storage.check_value("exists") is True

    def test_check_value_missing(self, lti_storage):
        """check_value returns False for missing keys."""
        assert lti_storage.check_value("missing") is False

    def test_key_prefix(self, lti_storage, fake_redis_client):
        """Keys are stored with the 'lti1p3:' prefix in Redis."""
        lti_storage.set_value("mykey", {"v": 1}, exp=60)
        raw = fake_redis_client.get("lti1p3:mykey")
        assert raw is not None
        assert json.loads(raw) == {"v": 1}

    def test_can_set_keys_expiration(self, lti_storage):
        """Storage advertises TTL support."""
        assert lti_storage.can_set_keys_expiration() is True

    def test_overwrite_value(self, lti_storage):
        """Writing the same key overwrites the previous value."""
        lti_storage.set_value("k", {"version": 1}, exp=60)
        lti_storage.set_value("k", {"version": 2}, exp=60)
        assert lti_storage.get_value("k") == {"version": 2}

    def test_default_ttl_used_when_exp_none(self, lti_storage, fake_redis_client):
        """When exp is None, the default TTL (7200s) is used."""
        lti_storage.set_value("ttl-test", {"v": 1})
        ttl = fake_redis_client.ttl("lti1p3:ttl-test")
        assert ttl > 0
        assert ttl <= 7200
