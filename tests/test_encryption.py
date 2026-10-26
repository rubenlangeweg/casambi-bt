import os

import pytest
from cryptography.exceptions import InvalidSignature

from CasambiBt._encryption import Encryptor, _xor


def test_xor():
    a = b"\x01\x02\x03"
    b = b"\x04\x05\x06"
    # 1^4=5, 2^5=7, 3^6=5
    expected = b"\x05\x07\x05"
    assert _xor(a, b) == expected


def test_xor_mismatched_length():
    a = b"\x01"
    b = b"\x01\x02"
    with pytest.raises(AssertionError):
        _xor(a, b)


def test_encryptor_init():
    key = os.urandom(16)
    encryptor = Encryptor(key)
    assert encryptor is not None


def test_encrypt_decrypt_roundtrip():
    key = os.urandom(16)
    encryptor = Encryptor(key)

    header = b"\x01\x02\x03\x04"
    body = b"some_payload_data"
    packet = header + body
    nonce = os.urandom(16)

    encrypted = encryptor.encryptThenMac(packet, nonce)

    # Verify structure: header + encrypted_body + mac (16 bytes)
    assert len(encrypted) == len(packet) + 16
    assert encrypted[:4] == header

    decrypted = encryptor.decryptAndVerify(encrypted, nonce)

    assert decrypted == body


def test_decrypt_invalid_mac():
    key = os.urandom(16)
    encryptor = Encryptor(key)

    header = b"\x01\x02\x03\x04"
    body = b"test_data"
    packet = header + body
    nonce = os.urandom(16)

    encrypted = encryptor.encryptThenMac(packet, nonce)

    # Tamper with the MAC (last 16 bytes)
    tampered = encrypted[:-1] + bytes([(encrypted[-1] + 1) % 256])

    with pytest.raises(InvalidSignature):
        encryptor.decryptAndVerify(tampered, nonce)


def test_decrypt_invalid_header_manipulation():
    # If we change the header, the MAC verification should fail because
    # the header is authenticated (CMAC input includes the header part of the packet)

    key = os.urandom(16)
    encryptor = Encryptor(key)

    header = b"\x01\x02\x03\x04"
    body = b"test_data"
    packet = header + body
    nonce = os.urandom(16)

    encrypted = encryptor.encryptThenMac(packet, nonce)

    # Tamper with the header
    tampered = bytes([(encrypted[0] + 1) % 256]) + encrypted[1:]

    with pytest.raises(InvalidSignature):
        encryptor.decryptAndVerify(tampered, nonce)
