"""Compatibility proxy for cipher_engine.core.sharding."""

from cipher_engine.core.sharding import (
    SHARD_HEADER_FORMAT,
    SHARD_HEADER_SIZE,
    SHARD_MAGIC,
    assemble_shards,
    calculate_image_capacities,
    inspect_shard,
    shard_payload,
)

__all__ = [
    "SHARD_HEADER_FORMAT",
    "SHARD_HEADER_SIZE",
    "SHARD_MAGIC",
    "assemble_shards",
    "calculate_image_capacities",
    "inspect_shard",
    "shard_payload",
]
