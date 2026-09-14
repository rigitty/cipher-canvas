"""Compatibility proxy for cipher_engine.core.lsb."""

from cipher_engine.core.lsb import (
    embed_bit,
    embed_bits,
    embed_byte,
    extract_bit,
    extract_bits,
    extract_byte,
)

__all__ = [
    "embed_bit",
    "embed_bits",
    "embed_byte",
    "extract_bit",
    "extract_bits",
    "extract_byte",
]
