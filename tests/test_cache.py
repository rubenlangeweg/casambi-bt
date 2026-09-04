"""Regression coverage for cache version compatibility."""

import asyncio
import pathlib
import pickle
from unittest.mock import AsyncMock

import pytest

from CasambiBt._cache import CACHE_VERSION, Cache
from CasambiBt._network import TYPES_CACHE_FILE, Network
from CasambiBt._unit import UnitControlType


def _seed_cache(cache_path: pathlib.Path, version: int, uuid: str) -> pathlib.Path:
    cache_path.mkdir(exist_ok=True)
    (cache_path / ".cachever").write_text(str(version))
    network_cache_path = cache_path / uuid
    network_cache_path.mkdir()
    stale_file = network_cache_path / "stale"
    stale_file.write_text("cached data")
    return stale_file


async def _open_cache(cache_path: pathlib.Path, uuid: str) -> None:
    cache = Cache(cache_path)
    await cache.setUuid(uuid)
    async with cache:
        pass


@pytest.mark.parametrize("version", [CACHE_VERSION - 1, CACHE_VERSION + 1])
def test_cache_version_mismatch_recreates_cache(
    tmp_path: pathlib.Path, version: int
) -> None:
    """Both upgrades and downgrades must discard incompatible cached objects."""
    uuid = "test-network"
    stale_file = _seed_cache(tmp_path, version, uuid)

    asyncio.run(_open_cache(tmp_path, uuid))

    assert not stale_file.exists()
    assert (tmp_path / ".cachever").read_text() == str(CACHE_VERSION)


def test_equal_cache_version_preserves_cache(tmp_path: pathlib.Path) -> None:
    """A cache with the current schema remains reusable."""
    uuid = "test-network"
    cached_file = _seed_cache(tmp_path, CACHE_VERSION, uuid)

    asyncio.run(_open_cache(tmp_path, uuid))

    assert cached_file.read_text() == "cached data"


def test_newer_cache_with_unknown_enum_is_deleted_before_unpickling(
    tmp_path: pathlib.Path,
) -> None:
    """A beta cache must not expose stable code to its value-98 enum member."""
    uuid = "test-network"
    _seed_cache(tmp_path, CACHE_VERSION + 1, uuid)

    stable_pickle = pickle.dumps(UnitControlType.DIMMER, protocol=4)
    enum_value = b"K\x00\x85\x94R"
    assert stable_pickle.count(enum_value) == 1
    stale_beta_pickle = stable_pickle.replace(enum_value, b"Kb\x85\x94R")

    with pytest.raises(ValueError, match="98 is not a valid UnitControlType"):
        pickle.loads(stale_beta_pickle)

    types_cache = tmp_path / uuid / TYPES_CACHE_FILE
    types_cache.write_bytes(stale_beta_pickle)

    async def load_network() -> Network:
        cache = Cache(tmp_path)
        await cache.setUuid(uuid)
        network = Network(uuid, AsyncMock(), cache)
        await network.load()
        return network

    network = asyncio.run(load_network())

    assert network._unitTypes == {}
    assert not types_cache.exists()
    assert (tmp_path / ".cachever").read_text() == str(CACHE_VERSION)
    assert 98 not in {control_type.value for control_type in UnitControlType}
