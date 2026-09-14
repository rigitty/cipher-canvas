import os
from typing import Literal

from argon2 import low_level
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

SALT_SIZE = 16
NONCE_SIZE = 12
TAG_SIZE = 16
KEY_SIZE = 32

# PBKDF2 Legacy Parameters
PBKDF2_ITERATIONS = 200_000

# Argon2id Parameters (RFC 9106 recommended for password hashing & key derivation)
ARGON2_TIME_COST = 2
ARGON2_MEMORY_COST = 64 * 1024  # 64 MB
ARGON2_PARALLELISM = 4

KdfType = Literal["argon2id", "pbkdf2"]


def zeroize(*buffers: bytearray | memoryview | None) -> None:
    """Securely wipes mutable memory buffers with zeros to prevent RAM dump forensics."""
    for b in buffers:
        if isinstance(b, bytearray):
            for i in range(len(b)):
                b[i] = 0
        elif isinstance(b, memoryview) and not b.readonly:
            b[:] = b"\x00" * len(b)


def derive_key_argon2(passphrase: str, salt: bytes) -> bytes:
    """Derives a 256-bit symmetric key using GPU/ASIC-resistant Argon2id (RFC 9106)."""
    return low_level.hash_secret_raw(
        secret=passphrase.encode("utf-8"),
        salt=salt,
        time_cost=ARGON2_TIME_COST,
        memory_cost=ARGON2_MEMORY_COST,
        parallelism=ARGON2_PARALLELISM,
        hash_len=KEY_SIZE,
        type=low_level.Type.ID,
    )


def derive_key_pbkdf2(passphrase: str, salt: bytes) -> bytes:
    """Derives a 256-bit symmetric key using PBKDF2-HMAC-SHA256 (legacy fallback)."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def derive_key(passphrase: str, salt: bytes, kdf_type: KdfType = "argon2id") -> bytes:
    """Derives a 256-bit AES key using either modern Argon2id or legacy PBKDF2."""
    if kdf_type == "argon2id":
        return derive_key_argon2(passphrase, salt)
    return derive_key_pbkdf2(passphrase, salt)


def seal(passphrase: str, plaintext: bytes, kdf_type: KdfType = "argon2id") -> bytes:
    """Encrypts plaintext with AES-256-GCM using Argon2id or PBKDF2 derived key."""
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key_buf = bytearray(derive_key(passphrase, salt, kdf_type=kdf_type))
    try:
        encrypted = AESGCM(bytes(key_buf)).encrypt(nonce, plaintext, None)
        return salt + nonce + encrypted
    finally:
        zeroize(key_buf)


def open_sealed(passphrase: str, sealed: bytes) -> bytes:
    """Decrypts AES-256-GCM payload with automatic Argon2id -> PBKDF2 fallback."""
    if len(sealed) < (SALT_SIZE + NONCE_SIZE + TAG_SIZE):
        raise ValueError("Sealed payload is too short to be valid ciphertext.")

    salt = sealed[:SALT_SIZE]
    nonce = sealed[SALT_SIZE : SALT_SIZE + NONCE_SIZE]
    encrypted = sealed[SALT_SIZE + NONCE_SIZE :]

    # 1. First attempt: Modern Argon2id
    key_buf = bytearray(derive_key_argon2(passphrase, salt))
    try:
        return AESGCM(bytes(key_buf)).decrypt(nonce, encrypted, None)
    except Exception:
        # 2. Fallback attempt: Legacy PBKDF2 (for backward compatibility)
        zeroize(key_buf)
        key_buf = bytearray(derive_key_pbkdf2(passphrase, salt))
        try:
            return AESGCM(bytes(key_buf)).decrypt(nonce, encrypted, None)
        finally:
            zeroize(key_buf)
    finally:
        zeroize(key_buf)
