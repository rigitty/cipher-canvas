"""Compatibility proxy for cipher_engine.core.crypto."""

from cipher_engine.core.crypto import (
    KEY_SIZE,
    NONCE_SIZE,
    PBKDF2_ITERATIONS,
    SALT_SIZE,
    TAG_SIZE,
    derive_key,
    open_sealed,
    seal,
    zeroize,
)

__all__ = [
    "KEY_SIZE",
    "NONCE_SIZE",
    "PBKDF2_ITERATIONS",
    "SALT_SIZE",
    "TAG_SIZE",
    "derive_key",
    "open_sealed",
    "seal",
    "zeroize",
]
