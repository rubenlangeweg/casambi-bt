"""Tests for the KeyStore module."""

import pickle
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest

from CasambiBt._cache import Cache
from CasambiBt._keystore import KEY_CACHE_FILE, KeyStore


@pytest.fixture
def cache(tmp_path: Path) -> Cache:
    """Provide a cache instance for testing."""
    return Cache(tmp_path)


@pytest.fixture(autouse=True)
async def setup_cache(cache: Cache) -> AsyncGenerator[None, None]:
    """Set up the cache for tests."""
    await cache.setUuid("test-uuid")
    await cache.invalidateCache()
    yield


async def test_keystore_add_key_valid(cache: Cache):
    """Test adding a valid key."""
    ks = KeyStore(cache)
    key_dict = {
        "id": "1",
        "type": "2",
        "role": "3",
        "name": "Test Key",
        "key": "0102030a0b0c",
    }
    await ks.addKey(key_dict)

    assert len(ks._keys) == 1
    key = ks._keys[0]
    assert key.id == 1
    assert key.type == 2
    assert key.role == 3
    assert key.name == "Test Key"
    assert key.key == b"\x01\x02\x03\x0a\x0b\x0c"

    # Verify it was saved
    async with cache as cache_path:
        key_bytes = await (cache_path / KEY_CACHE_FILE).read_bytes()
        loaded_keys = pickle.loads(key_bytes)
        assert len(loaded_keys) == 1
        assert loaded_keys[0].id == 1


async def test_keystore_add_key_missing_fields(cache: Cache):
    """Test adding keys with missing fields."""
    ks = KeyStore(cache)

    with pytest.raises(KeyError, match="id"):
        await ks.addKey({})

    with pytest.raises(KeyError, match="type"):
        await ks.addKey({"id": "1"})

    with pytest.raises(KeyError, match="role"):
        await ks.addKey({"id": "1", "type": "2"})

    with pytest.raises(KeyError, match="name"):
        await ks.addKey({"id": "1", "type": "2", "role": "3"})

    with pytest.raises(KeyError, match="key"):
        await ks.addKey({"id": "1", "type": "2", "role": "3", "name": "Test"})


async def test_keystore_add_key_invalid_fields(cache: Cache):
    """Test adding keys with invalid fields."""
    ks = KeyStore(cache)

    with pytest.raises(ValueError, match="id"):
        await ks.addKey(
            {"id": "-1", "type": "2", "role": "3", "name": "Test", "key": "00"}
        )

    with pytest.raises(ValueError, match="type"):
        await ks.addKey(
            {"id": "1", "type": "-1", "role": "3", "name": "Test", "key": "00"}
        )

    with pytest.raises(ValueError, match="type"):
        await ks.addKey(
            {"id": "1", "type": "256", "role": "3", "name": "Test", "key": "00"}
        )

    with pytest.raises(ValueError, match="role"):
        await ks.addKey(
            {"id": "1", "type": "2", "role": "-1", "name": "Test", "key": "00"}
        )

    with pytest.raises(ValueError, match="role"):
        await ks.addKey(
            {"id": "1", "type": "2", "role": "4", "name": "Test", "key": "00"}
        )

    with pytest.raises(ValueError, match="key"):
        await ks.addKey(
            {"id": "1", "type": "2", "role": "3", "name": "Test", "key": "invalid_hex"}
        )


async def test_keystore_add_key_duplicate_id(cache: Cache):
    """Test adding a key with an existing id."""
    ks = KeyStore(cache)
    key_dict = {"id": "1", "type": "2", "role": "3", "name": "Test", "key": "00"}
    await ks.addKey(key_dict)
    assert len(ks._keys) == 1

    # Add duplicate
    await ks.addKey(key_dict)
    assert len(ks._keys) == 1  # Should not add another


async def test_keystore_load(cache: Cache):
    """Test loading keys from cache."""
    ks1 = KeyStore(cache)
    await ks1.addKey({"id": "1", "type": "2", "role": "3", "name": "Test", "key": "00"})

    ks2 = KeyStore(cache)
    await ks2.load()
    assert len(ks2._keys) == 1
    assert ks2._keys[0].id == 1


async def test_keystore_load_no_file(cache: Cache):
    """Test loading when cache file does not exist."""
    ks = KeyStore(cache)
    await ks.load()
    assert ks._keys == []


async def test_keystore_clear(cache: Cache):
    """Test clearing keys."""
    ks = KeyStore(cache)
    await ks.addKey({"id": "1", "type": "2", "role": "3", "name": "Test", "key": "00"})
    assert len(ks._keys) == 1

    await ks.clear(save=False)
    assert len(ks._keys) == 0

    # Cache should still have it since save=False
    ks2 = KeyStore(cache)
    await ks2.load()
    assert len(ks2._keys) == 1

    await ks.clear(save=True)
    assert len(ks._keys) == 0

    ks3 = KeyStore(cache)
    await ks3.load()
    assert len(ks3._keys) == 0


async def test_keystore_get_key(cache: Cache):
    """Test getting the key with the highest role."""
    ks = KeyStore(cache)
    assert ks.getKey() is None

    await ks.addKey({"id": "1", "type": "2", "role": "1", "name": "Test1", "key": "00"})
    key1 = ks.getKey()
    assert key1 is not None and key1.id == 1

    await ks.addKey({"id": "2", "type": "2", "role": "3", "name": "Test2", "key": "00"})
    key2 = ks.getKey()
    assert key2 is not None and key2.id == 2

    await ks.addKey({"id": "3", "type": "2", "role": "2", "name": "Test3", "key": "00"})
    key3 = ks.getKey()
    assert key3 is not None and key3.id == 2
