import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

SALT_SIZE = 16
NONCE_SIZE = 12
TAG_SIZE = 16
KEY_SIZE = 32
PBKDF2_ITERATIONS = 200_000


def zeroize(*buffers: bytearray | memoryview | None) -> None:
    """Securely wipes mutable memory buffers with zeros to prevent RAM dump forensics."""
    for b in buffers:
        if isinstance(b, bytearray):
            for i in range(len(b)):
                b[i] = 0
        elif isinstance(b, memoryview) and not b.readonly:
            b[:] = b"\x00" * len(b)


def derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def seal(passphrase: str, plaintext: bytes) -> bytes:
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key_buf = bytearray(derive_key(passphrase, salt))
    try:
        encrypted = AESGCM(bytes(key_buf)).encrypt(nonce, plaintext, None)
        return salt + nonce + encrypted
    finally:
        zeroize(key_buf)


def open_sealed(passphrase: str, sealed: bytes) -> bytes:
    salt = sealed[:SALT_SIZE]
    nonce = sealed[SALT_SIZE : SALT_SIZE + NONCE_SIZE]
    encrypted = sealed[SALT_SIZE + NONCE_SIZE :]
    key_buf = bytearray(derive_key(passphrase, salt))
    try:
        return AESGCM(bytes(key_buf)).decrypt(nonce, encrypted, None)
    finally:
        zeroize(key_buf)
