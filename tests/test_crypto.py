import pytest
from cryptography.exceptions import InvalidTag

from cipher_engine.core import crypto


def test_seal_and_open_argon2id(passphrase: str):
    message = b"Top secret payload protected by Argon2id"
    sealed = crypto.seal(passphrase, message, kdf_type="argon2id")
    assert len(sealed) == len(message) + crypto.SALT_SIZE + crypto.NONCE_SIZE + crypto.TAG_SIZE

    recovered = crypto.open_sealed(passphrase, sealed)
    assert recovered == message


def test_seal_and_open_pbkdf2(passphrase: str):
    message = b"Legacy PBKDF2 HMAC SHA256 payload"
    sealed = crypto.seal(passphrase, message, kdf_type="pbkdf2")
    recovered = crypto.open_sealed(passphrase, sealed)
    assert recovered == message


def test_tampered_ciphertext_rejected(passphrase: str):
    message = b"Authenticated encryption integrity test"
    sealed = bytearray(crypto.seal(passphrase, message))
    # Corrupt the last byte of the GCM authentication tag
    sealed[-1] ^= 0x01

    with pytest.raises((InvalidTag, ValueError)):
        crypto.open_sealed(passphrase, bytes(sealed))


def test_wrong_passphrase_rejected(passphrase: str):
    message = b"Secret data"
    sealed = crypto.seal(passphrase, message)
    with pytest.raises((InvalidTag, ValueError)):
        crypto.open_sealed("wrong-passphrase-attempt", sealed)


def test_zeroize():
    buf = bytearray(b"sensitive-private-key-material")
    crypto.zeroize(buf)
    assert buf == bytearray(len(buf))
