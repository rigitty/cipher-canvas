import io
import math
import struct
import uuid
import zlib
from typing import List, Tuple
from PIL import Image

import capacity
import crypto
import stego

SHARD_MAGIC = b"CCSH"  # Cipher Canvas Shard
SHARD_HEADER_FORMAT = ">4s16sHHII"  # MAGIC(4), UUID(16), SHARD_IDX(2), TOTAL_SHARDS(2), CRC32(4), TOTAL_SIZE(4)
SHARD_HEADER_SIZE = struct.calcsize(SHARD_HEADER_FORMAT)  # 32 bytes


def calculate_image_capacities(images: List[Image.Image], bit_depth: int = 1) -> List[int]:
    capacities = []
    for img in images:
        norm_img, is_rgba = stego._normalize_image(img)
        w, h = norm_img.size
        slots_count = w * h * 3
        available_slots = max(0, slots_count - 72)
        max_sealed = (available_slots * bit_depth) // 8
        usable = max(0, int((max_sealed - 64) / 1.45) - SHARD_HEADER_SIZE - 20)
        capacities.append(usable)
    return capacities


def shard_payload(
    passphrase: str,
    filename: str,
    payload_data: bytes,
    carrier_images: List[Image.Image],
    bit_depth: int = 1,
) -> List[Image.Image]:
    if len(carrier_images) < 2:
        raise ValueError("Multi-image sharding requires at least 2 carrier images.")

    bit_depth = max(1, min(4, int(bit_depth)))
    total_shards = len(carrier_images)
    group_id = uuid.uuid4().bytes
    full_packed = stego.pack_payload(filename, payload_data)
    total_size = len(full_packed)
    payload_crc = zlib.crc32(full_packed) & 0xFFFFFFFF

    capacities = calculate_image_capacities(carrier_images, bit_depth)
    total_capacity = sum(capacities)
    if total_size > total_capacity:
        raise ValueError(
            f"Total payload size ({total_size} B) exceeds combined capacity ({total_capacity} B) of the {total_shards} carrier images."
        )

    shards_data = []
    offset = 0
    for i, cap in enumerate(capacities):
        if i == total_shards - 1:
            chunk = full_packed[offset:]
        else:
            ratio = cap / total_capacity if total_capacity > 0 else 1.0 / total_shards
            chunk_size = int(math.ceil(total_size * ratio))
            chunk_size = min(chunk_size, len(full_packed) - offset)
            chunk = full_packed[offset : offset + chunk_size]
            offset += chunk_size
        shards_data.append(chunk)

    stego_images = []
    for idx, (img, chunk) in enumerate(zip(carrier_images, shards_data)):
        header = struct.pack(
            SHARD_HEADER_FORMAT,
            SHARD_MAGIC,
            group_id,
            idx,
            total_shards,
            payload_crc,
            total_size,
        )
        shard_payload_block = header + chunk
        stego_img, _ = stego._embed_bytes(
            passphrase, shard_payload_block, img, bit_depth=bit_depth
        )
        stego_images.append(stego_img)

    return stego_images


def inspect_shard(passphrase: str, image: Image.Image) -> dict | None:
    try:
        raw_bytes = stego._extract_bytes(passphrase, image)
        if len(raw_bytes) < SHARD_HEADER_SIZE:
            return None
        magic, group_id, shard_idx, total_shards, payload_crc, total_size = struct.unpack(
            SHARD_HEADER_FORMAT, raw_bytes[:SHARD_HEADER_SIZE]
        )
        if magic != SHARD_MAGIC:
            return None
        return {
            "group_id": group_id.hex(),
            "shard_index": shard_idx,
            "total_shards": total_shards,
            "crc32": payload_crc,
            "total_size": total_size,
            "chunk_data": raw_bytes[SHARD_HEADER_SIZE:],
        }
    except Exception:
        return None


def assemble_shards(
    passphrase: str, shard_images: List[Image.Image]
) -> Tuple[str, bytes, dict]:
    if not shard_images:
        raise ValueError("No images provided for reassembly.")

    parsed_shards = []
    for img in shard_images:
        meta = inspect_shard(passphrase, img)
        if meta is not None:
            parsed_shards.append(meta)

    if not parsed_shards:
        raise ValueError("None of the provided images contain valid shard data with this passphrase.")

    groups = {}
    for s in parsed_shards:
        gid = s["group_id"]
        groups.setdefault(gid, []).append(s)

    target_group_id = max(groups.keys(), key=lambda g: len(groups[g]))
    group_shards = groups[target_group_id]

    expected_total = group_shards[0]["total_shards"]
    expected_crc = group_shards[0]["crc32"]
    expected_size = group_shards[0]["total_size"]

    shards_by_idx = {s["shard_index"]: s for s in group_shards}

    missing_indices = [i for i in range(expected_total) if i not in shards_by_idx]
    if missing_indices:
        missing_str = ", ".join(f"#{i+1}" for i in missing_indices)
        raise ValueError(
            f"Incomplete shard set: Found {len(shards_by_idx)} of {expected_total} shards. Missing shard(s): {missing_str}."
        )

    sorted_chunks = [shards_by_idx[i]["chunk_data"] for i in range(expected_total)]
    assembled_packed = b"".join(sorted_chunks)

    actual_crc = zlib.crc32(assembled_packed) & 0xFFFFFFFF
    if actual_crc != expected_crc or len(assembled_packed) != expected_size:
        raise ValueError(
            "Integrity check failed: Reassembled data corrupted (CRC mismatch or length discrepancy)."
        )

    filename, data = stego.unpack_payload(assembled_packed)
    report = {
        "group_id": target_group_id,
        "total_shards": expected_total,
        "filename": filename,
        "size_bytes": len(data),
    }
    return filename, data, report
