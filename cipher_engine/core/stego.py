import math

import numpy as np
import zstandard
from PIL import Image

from cipher_engine.core import crypto, prng

MAGIC = b"CSG2"
MAGIC_V1 = b"CSGA"
MAGIC_LEN = 4
HEADER_SIZE = 9  # MAGIC (4) + bit_depth (1) + length (4)

ZSTD_HEADER_PREFIX = b"ZSTD\x00"


def bytes_to_bits(data: bytes) -> list[int]:
    bits: list[int] = []
    for byte in data:
        for i in range(8):
            bits.append((byte >> i) & 0x01)
    return bits


def bits_to_bytes(bits: list[int]) -> bytes:
    out = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(8):
            if i + j < len(bits):
                byte |= bits[i + j] << j
        out.append(byte)
    return bytes(out)


def bytes_to_chunked_bits(data: bytes, b: int) -> list[int]:
    out: list[int] = []
    bit_buf = 0
    bit_count = 0
    for byte in data:
        for i in range(8):
            bit = (byte >> i) & 1
            bit_buf |= bit << bit_count
            bit_count += 1
            if bit_count == b:
                out.append(bit_buf)
                bit_buf = 0
                bit_count = 0
    if bit_count > 0:
        out.append(bit_buf)
    return out


def chunked_bits_to_bytes(chunks: list[int], b: int, total_bytes: int) -> bytes:
    out = bytearray()
    byte_val = 0
    bit_count = 0
    for chunk in chunks:
        for i in range(b):
            bit = (chunk >> i) & 1
            byte_val |= bit << bit_count
            bit_count += 1
            if bit_count == 8:
                out.append(byte_val)
                byte_val = 0
                bit_count = 0
                if len(out) == total_bytes:
                    return bytes(out)
    return bytes(out)


def pack_payload(filename: str, data: bytes, compress: bool = False) -> bytes:
    encoded_name = filename.encode("utf-8")
    if compress and len(data) > 32:
        try:
            cctx = zstandard.ZstdCompressor(level=3)
            compressed = cctx.compress(data)
            if len(compressed) + len(ZSTD_HEADER_PREFIX) < len(data):
                return encoded_name + b"\x00" + ZSTD_HEADER_PREFIX + compressed
        except Exception:
            pass
    return encoded_name + b"\x00" + data


def unpack_payload(payload: bytes) -> tuple[str, bytes]:
    parts = payload.split(b"\x00", 1)
    if len(parts) == 1:
        filename = "message.txt"
        raw = payload
    else:
        filename = parts[0].decode("utf-8", errors="replace").strip() or "file.bin"
        raw = parts[1]

    if raw.startswith(ZSTD_HEADER_PREFIX):
        try:
            dctx = zstandard.ZstdDecompressor()
            decompressed = dctx.decompress(raw[len(ZSTD_HEADER_PREFIX) :])
            return filename, decompressed
        except Exception:
            pass

    return filename, raw


def _normalize_image(image: Image.Image) -> tuple[Image.Image, bool]:
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        return image.convert("RGBA"), True
    return image.convert("RGB"), False


def _get_slot_indices(arr: np.ndarray, is_rgba: bool) -> np.ndarray:
    if is_rgba:
        alpha = arr[:, :, 3].reshape(-1)
        valid_pixels = np.where(alpha >= 10)[0]
        slot_indices = np.empty((len(valid_pixels), 3), dtype=np.int64)
        slot_indices[:, 0] = valid_pixels * 4
        slot_indices[:, 1] = valid_pixels * 4 + 1
        slot_indices[:, 2] = valid_pixels * 4 + 2
        return slot_indices.reshape(-1)
    return np.arange(arr.size, dtype=np.int64)


def _embed_bytes(
    passphrase: str, payload: bytes, image: Image.Image, bit_depth: int = 1
) -> tuple[Image.Image, int]:
    bit_depth = max(1, min(4, int(bit_depth)))
    norm_img, is_rgba = _normalize_image(image)
    arr = np.array(norm_img, dtype=np.uint8)
    flat_arr = arr.reshape(-1)
    slot_flat_indices = _get_slot_indices(arr, is_rgba)

    sealed = crypto.seal(passphrase, payload)
    header = MAGIC + bytes([bit_depth]) + len(sealed).to_bytes(4, "big")
    header_bits = np.array(bytes_to_bits(header), dtype=np.uint8)
    payload_chunks = np.array(bytes_to_chunked_bits(sealed, bit_depth), dtype=np.uint8)

    needed_slots = len(header_bits) + len(payload_chunks)
    if needed_slots > len(slot_flat_indices):
        raise ValueError(
            f"payload too large: needs {needed_slots} slots, have {len(slot_flat_indices)} available slots"
        )

    order = np.array(
        prng.build_permutation(prng.derive_seed(passphrase), len(slot_flat_indices)),
        dtype=np.int64,
    )

    # 1. Embed header (always 1 bit per slot for universal detection)
    h_slots = slot_flat_indices[order[: len(header_bits)]]
    flat_arr[h_slots] = (flat_arr[h_slots] & 0xFE) | header_bits

    # 2. Embed payload with chosen bit_depth per slot
    p_slots = slot_flat_indices[order[len(header_bits) : needed_slots]]
    mask = (~((1 << bit_depth) - 1)) & 0xFF
    flat_arr[p_slots] = (flat_arr[p_slots] & mask) | payload_chunks

    mode = "RGBA" if is_rgba else "RGB"
    out = Image.fromarray(arr, mode=mode)
    total_bits = len(header_bits) + len(payload_chunks) * bit_depth
    return out, total_bits


def _extract_bytes(passphrase: str, image: Image.Image) -> bytes:
    norm_img, is_rgba = _normalize_image(image)
    arr = np.array(norm_img, dtype=np.uint8)
    flat_arr = arr.reshape(-1)
    slot_flat_indices = _get_slot_indices(arr, is_rgba)

    if len(slot_flat_indices) < 64:
        raise ValueError("carrier image too small for stego header")

    order = np.array(
        prng.build_permutation(prng.derive_seed(passphrase), len(slot_flat_indices)),
        dtype=np.int64,
    )

    # Lazy read: extract first 72 bits to check v2 header (or 64 for v1 fallback)
    read_limit = min(72, len(slot_flat_indices))
    h_slots = slot_flat_indices[order[:read_limit]]
    header_bits = list(flat_arr[h_slots] & 0x01)
    header_bytes = bits_to_bytes(header_bits)

    if header_bytes[:4] == MAGIC:
        bit_depth = header_bytes[4]
        if bit_depth < 1 or bit_depth > 4:
            raise ValueError("unsupported bit depth in header")
        sealed_len = int.from_bytes(header_bytes[5:9], "big")
        header_slots = 72
    elif header_bytes[:4] == MAGIC_V1:
        bit_depth = 1
        sealed_len = int.from_bytes(header_bytes[4:8], "big")
        header_slots = 64
    else:
        raise ValueError("header magic not found (wrong passphrase or image is not a carrier)")

    needed_chunks = math.ceil(sealed_len * 8 / bit_depth)
    if header_slots + needed_chunks > len(slot_flat_indices):
        raise ValueError("corrupted length in header (exceeds available image slots)")

    p_slots = slot_flat_indices[order[header_slots : header_slots + needed_chunks]]
    mask = (1 << bit_depth) - 1
    chunks = list(flat_arr[p_slots] & mask)

    sealed = chunked_bits_to_bytes(chunks, bit_depth, sealed_len)
    return crypto.open_sealed(passphrase, sealed)


def encode(
    passphrase: str,
    message: str,
    carrier_path: str,
    output_path: str,
    bit_depth: int = 1,
    compress: bool = False,
) -> int:
    image = Image.open(carrier_path)
    payload = pack_payload("message.txt", message.encode("utf-8"), compress=compress)
    output_image, bits = _embed_bytes(passphrase, payload, image, bit_depth=bit_depth)
    output_image.save(output_path)
    return bits


def decode(passphrase: str, carrier_path: str) -> str:
    image = Image.open(carrier_path)
    filename, data = unpack_payload(_extract_bytes(passphrase, image))
    return data.decode("utf-8", errors="replace")
