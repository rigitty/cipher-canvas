import math
import struct
import uuid
import zlib

import numpy as np
from PIL import Image

from cipher_engine.core import stego

SHARD_MAGIC = b"CCSH"  # Cipher Canvas Shard
SHARD_HEADER_FORMAT = ">4s16sHHII"  # MAGIC(4), UUID(16), SHARD_IDX(2), TOTAL_SHARDS(2), CRC32(4), TOTAL_SIZE(4)
SHARD_HEADER_SIZE = struct.calcsize(SHARD_HEADER_FORMAT)  # 32 bytes


def calculate_image_capacities(images: list[Image.Image], bit_depth: int = 1) -> list[int]:
    capacities = []
    num_shards = len(images)
    for img in images:
        norm_img, is_rgba = stego._normalize_image(img)
        arr = np.array(norm_img, dtype=np.uint8)
        slot_indices = stego._get_slot_indices(arr, is_rgba)
        available_slots = len(slot_indices) - 72
        if available_slots <= 0:
            capacities.append(0)
            continue
        max_sealed = (available_slots * bit_depth) // 8
        shard_env = len(f"shard_{num_shards}_of_{num_shards}.bin".encode()) + 1 + SHARD_HEADER_SIZE + 44
        usable = max(0, max_sealed - shard_env - 16)
        capacities.append(usable)
    return capacities


def shard_payload(
    passphrase: str,
    filename: str,
    payload_data: bytes,
    carrier_images: list[Image.Image],
    bit_depth: int = 1,
    compress: bool = False,
) -> list[Image.Image]:
    if len(carrier_images) < 2:
        raise ValueError("Multi-image sharding requires at least 2 carrier images.")

    packed_payload = stego.pack_payload(filename, payload_data, compress=compress)
    total_size = len(packed_payload)
    crc = zlib.crc32(packed_payload) & 0xFFFFFFFF
    group_id = uuid.uuid4().bytes
    num_shards = len(carrier_images)

    capacities = calculate_image_capacities(carrier_images, bit_depth)
    total_capacity = sum(capacities)
    if total_size > total_capacity:
        raise ValueError(
            f"Payload too large for provided images ({total_size:,} bytes > total capacity {total_capacity:,} bytes)."
        )

    # Check if any carrier is too small to participate
    for idx, cap in enumerate(capacities):
        if cap <= 0:
            img = carrier_images[idx]
            raise ValueError(
                f"Carrier #{idx + 1} ({img.width}x{img.height}) is too small to store a shard header. "
                f"Please choose a higher-resolution image."
            )

    # Capacity-proportional chunking: allocates shard sizes proportional to each carrier's capacity
    chunks = []
    remaining_data = packed_payload
    remaining_capacity = total_capacity

    for i in range(num_shards):
        if i == num_shards - 1:
            chunk = remaining_data
        else:
            cap = capacities[i]
            target = int(math.floor(total_size * (cap / total_capacity))) if total_capacity > 0 else 0
            # Ensure remainder doesn't exceed total capacity of future carriers
            min_needed = max(0, len(remaining_data) - (remaining_capacity - cap))
            target = max(target, min_needed)
            target = max(0, min(target, cap, len(remaining_data)))
            chunk = remaining_data[:target]
            remaining_data = remaining_data[target:]
            remaining_capacity -= cap
        chunks.append(chunk)

    stego_images = []
    for idx, (carrier, chunk) in enumerate(zip(carrier_images, chunks)):
        header = struct.pack(
            SHARD_HEADER_FORMAT,
            SHARD_MAGIC,
            group_id,
            idx,
            num_shards,
            crc,
            total_size,
        )
        shard_data = header + chunk
        shard_filename = f"shard_{idx + 1}_of_{num_shards}.bin"
        packed_shard = stego.pack_payload(shard_filename, shard_data, compress=False)

        stego_img, _ = stego._embed_bytes(
            passphrase=passphrase,
            payload=packed_shard,
            image=carrier,
            bit_depth=bit_depth,
        )
        stego_images.append(stego_img)

    return stego_images


def inspect_shard(passphrase: str, image: Image.Image) -> dict | None:
    try:
        raw = stego._extract_bytes(passphrase, image)
        _, data = stego.unpack_payload(raw)
        if len(data) < SHARD_HEADER_SIZE:
            return None
        magic, group_uuid, idx, total, crc, total_size = struct.unpack(
            SHARD_HEADER_FORMAT, data[:SHARD_HEADER_SIZE]
        )
        if magic != SHARD_MAGIC:
            return None
        return {
            "group_id": uuid.UUID(bytes=group_uuid).hex,
            "shard_index": idx,
            "total_shards": total,
            "crc32": crc,
            "total_size": total_size,
        }
    except Exception:
        return None


def assemble_shards(
    passphrase: str,
    shard_images: list[Image.Image],
) -> tuple[str, bytes, dict]:
    if not shard_images:
        raise ValueError("No shard images provided.")

    extracted_shards = []
    for img in shard_images:
        try:
            raw = stego._extract_bytes(passphrase, img)
            _, data = stego.unpack_payload(raw)
            if len(data) < SHARD_HEADER_SIZE:
                raise ValueError("Payload too small for shard header")
            magic, group_uuid, idx, total, crc, total_size = struct.unpack(
                SHARD_HEADER_FORMAT, data[:SHARD_HEADER_SIZE]
            )
            if magic != SHARD_MAGIC:
                raise ValueError("Invalid shard magic")
            chunk = data[SHARD_HEADER_SIZE:]
            extracted_shards.append({
                "group_id": group_uuid,
                "idx": idx,
                "total": total,
                "crc": crc,
                "total_size": total_size,
                "chunk": chunk,
            })
        except Exception as exc:
            raise ValueError(f"Failed to decrypt shard: {exc}")

    first_group = extracted_shards[0]["group_id"]
    expected_total = extracted_shards[0]["total"]
    expected_crc = extracted_shards[0]["crc"]
    _expected_size = extracted_shards[0]["total_size"]

    for s in extracted_shards:
        if s["group_id"] != first_group:
            raise ValueError("Uploaded shards belong to different file groups.")
        if s["total"] != expected_total:
            raise ValueError("Shard total count mismatch.")

    if len(extracted_shards) < expected_total:
        missing = expected_total - len(extracted_shards)
        raise ValueError(
            f"Missing shards: received {len(extracted_shards)} of {expected_total} shards. (Need {missing} more)"
        )

    extracted_shards.sort(key=lambda x: x["idx"])
    indices = [s["idx"] for s in extracted_shards]
    if indices != list(range(expected_total)):
        raise ValueError(f"Duplicate or missing shard indices: {indices}")

    reassembled_payload = b"".join(s["chunk"] for s in extracted_shards)

    actual_crc = zlib.crc32(reassembled_payload) & 0xFFFFFFFF
    if actual_crc != expected_crc:
        raise ValueError("Integrity check failed: CRC32 checksum does not match!")

    filename, file_data = stego.unpack_payload(reassembled_payload)
    report = {
        "group_id": uuid.UUID(bytes=first_group).hex,
        "total_shards": expected_total,
        "total_size": len(file_data),
        "filename": filename,
    }
    return filename, file_data, report
