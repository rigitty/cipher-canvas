import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

SALT_SIZE = 16
NONCE_SIZE = 12
TAG_SIZE = 16
KEY_SIZE = 32
PBKDF2_ITERATIONS = 200_000


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
    key = derive_key(passphrase, salt)
    encrypted = AESGCM(key).encrypt(nonce, plaintext, None)
    return salt + nonce + encrypted


def open_sealed(passphrase: str, sealed: bytes) -> bytes:
    salt = sealed[:SALT_SIZE]
    nonce = sealed[SALT_SIZE : SALT_SIZE + NONCE_SIZE]
    encrypted = sealed[SALT_SIZE + NONCE_SIZE :]
    key = derive_key(passphrase, salt)
    return AESGCM(key).decrypt(nonce, encrypted, None)


def demo() -> None:
    message = b"top secret: meet at the pixel at midnight"
    passphrase = "correct horse battery staple"

    sealed = seal(passphrase, message)
    print(f"plaintext size : {len(message)} bytes")
    print(f"sealed size    : {len(sealed)} bytes  (overhead = {len(sealed) - len(message)})")

    recovered = open_sealed(passphrase, sealed)
    print(f"round-trip ok  : {recovered == message}")

    corrupted = bytearray(sealed)
    corrupted[len(corrupted) - 1] ^= 0x01
    try:
        open_sealed(passphrase, bytes(corrupted))
        print("tampering      : NOT DETECTED (bug!)")
    except Exception:
        print("tampering      : detected, decrypt failed (GCM tag)")

    try:
        open_sealed("wrong passphrase", sealed)
        print("wrong pass     : ACCEPTED (bug!)")
    except Exception:
        print("wrong pass     : rejected (GCM tag)")


if __name__ == "__main__":
    demo()
