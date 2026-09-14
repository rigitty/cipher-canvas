import io
import math
import struct
import uuid
import zlib
from typing import List, Tuple
from PIL import Image

from cipher_engine.core import capacity, crypto, stego

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

    packed_payload = stego.pack_payload(filename, payload_data)
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

    chunk_size = math.ceil(total_size / num_shards)
    chunks = []
    offset = 0
    for i in range(num_shards):
        if i == num_shards - 1:
            chunk = packed_payload[offset:]
        else:
            end = min(offset + chunk_size, total_size)
            chunk = packed_payload[offset:end]
            offset = end
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
        packed_shard = stego.pack_payload(shard_filename, shard_data)

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
    shard_images: List[Image.Image],
) -> Tuple[str, bytes, dict]:
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
    expected_size = extracted_shards[0]["total_size"]

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
