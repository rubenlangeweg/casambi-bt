"""Regression coverage for a GATT disconnect during a Casambi write."""

import asyncio
from unittest.mock import AsyncMock, Mock

from bleak.exc import BleakError
import pytest

from CasambiBt._client import CasambiClient
from CasambiBt._constants import ConnectionState
from CasambiBt.errors import ConnectionStateError


def test_disconnected_gatt_write_propagates_connection_state_error() -> None:
    """A swallowed write failure prevents the caller from running recovery."""
    client = CasambiClient.__new__(CasambiClient)
    client._connectionState = ConnectionState.AUTHENTICATED
    client._gattClient = AsyncMock()
    client._gattClient.write_gatt_char.side_effect = BleakError("Not connected")
    client._encryptor = Mock()
    client._encryptor.encryptThenMac.return_value = b"encrypted"
    client._nonce = b"1234567890123456"

    with pytest.raises(ConnectionStateError):
        asyncio.run(client._writeEncPacket(b"payload", 1, "characteristic"))

    assert client._connectionState == ConnectionState.NONE
