import random

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

DEFAULT_PRNG_SALT = b"cipher-canvas-prng-domain-v2"
PRNG_KDF_ROUNDS = 50_000


def derive_seed(passphrase: str, domain_salt: bytes = DEFAULT_PRNG_SALT) -> int:
    """Derives a cryptographically stretched 256-bit PRNG seed from passphrase with domain isolation."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=domain_salt,
        iterations=PRNG_KDF_ROUNDS,
    )
    seed_buf = bytearray(kdf.derive(passphrase.encode("utf-8")))
    try:
        return int.from_bytes(seed_buf, "big")
    finally:
        for i in range(len(seed_buf)):
            seed_buf[i] = 0


def build_permutation(seed: int, slot_count: int) -> list[int]:
    rng = random.Random(seed)
    permutation = list(range(slot_count))
    rng.shuffle(permutation)
    return permutation


def pick_slots(seed: int, slot_count: int, needed: int) -> list[int]:
    permutation = build_permutation(seed, slot_count)
    return permutation[:needed]
