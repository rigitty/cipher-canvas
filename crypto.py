"""Compatibility proxy for cipher_engine.core.crypto."""

from cipher_engine.core.crypto import (
    ARGON2_MEMORY_COST,
    ARGON2_PARALLELISM,
    ARGON2_TIME_COST,
    KEY_SIZE,
    NONCE_SIZE,
    PBKDF2_ITERATIONS,
    SALT_SIZE,
    TAG_SIZE,
    derive_key,
    derive_key_argon2,
    derive_key_pbkdf2,
    open_sealed,
    seal,
    zeroize,
)

__all__ = [
    "ARGON2_MEMORY_COST",
    "ARGON2_PARALLELISM",
    "ARGON2_TIME_COST",
    "KEY_SIZE",
    "NONCE_SIZE",
    "PBKDF2_ITERATIONS",
    "SALT_SIZE",
    "TAG_SIZE",
    "derive_key",
    "derive_key_argon2",
    "derive_key_pbkdf2",
    "open_sealed",
    "seal",
    "zeroize",
]
