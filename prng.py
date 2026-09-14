"""Compatibility proxy for cipher_engine.core.prng."""

from cipher_engine.core.prng import (
    DEFAULT_PRNG_SALT,
    PRNG_KDF_ROUNDS,
    build_permutation,
    derive_seed,
    pick_slots,
)

__all__ = [
    "DEFAULT_PRNG_SALT",
    "PRNG_KDF_ROUNDS",
    "build_permutation",
    "derive_seed",
    "pick_slots",
]
