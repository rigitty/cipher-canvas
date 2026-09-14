"""Compatibility proxy for cipher_engine.core.capacity."""

from cipher_engine.core.capacity import (
    AES_OVERHEAD,
    HEADER_BYTES,
    max_payload_bits,
    max_plaintext_bytes,
    max_robust_capacity_bytes,
)

__all__ = [
    "AES_OVERHEAD",
    "HEADER_BYTES",
    "max_payload_bits",
    "max_plaintext_bytes",
    "max_robust_capacity_bytes",
]
