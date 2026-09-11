import math
from PIL import Image

import crypto
import lsb
import prng

MAGIC = b"CSG2"
MAGIC_V1 = b"CSGA"
MAGIC_LEN = 4
HEADER_SIZE = 9  # MAGIC (4) + bit_depth (1) + length (4)


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


def pack_payload(filename: str, data: bytes) -> bytes:
    return filename.encode("utf-8") + b"\x00" + data


def unpack_payload(payload: bytes) -> tuple[str, bytes]:
    parts = payload.split(b"\x00", 1)
    if len(parts) == 1:
        return "message.txt", payload
    filename = parts[0].decode("utf-8", errors="replace").strip() or "file.bin"
    return filename, parts[1]


def _normalize_image(image: Image.Image) -> Image.Image:
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        return image.convert("RGBA")
    return image.convert("RGB")


def _get_slots(image: Image.Image) -> tuple[list[tuple[int, int]], bool, list]:
    image = _normalize_image(image)
    is_rgba = image.mode == "RGBA"
    pixels = list(image.get_flattened_data())
    slots: list[tuple[int, int]] = []

    if is_rgba:
        for p_idx, p in enumerate(pixels):
            # Alpha preservation: only embed in visible pixels (alpha >= 10)
            if p[3] >= 10:
                slots.append((p_idx, 0))
                slots.append((p_idx, 1))
                slots.append((p_idx, 2))
    else:
        for p_idx in range(len(pixels)):
            slots.append((p_idx, 0))
            slots.append((p_idx, 1))
            slots.append((p_idx, 2))

    return slots, is_rgba, pixels


def _embed_bytes(
    passphrase: str, payload: bytes, image: Image.Image, bit_depth: int = 1
) -> tuple[Image.Image, int]:
    bit_depth = max(1, min(4, int(bit_depth)))
    sealed = crypto.seal(passphrase, payload)
    header = MAGIC + bytes([bit_depth]) + len(sealed).to_bytes(4, "big")
    header_bits = bytes_to_bits(header)
    payload_chunks = bytes_to_chunked_bits(sealed, bit_depth)

    slots, is_rgba, pixels = _get_slots(image)
    needed_slots = len(header_bits) + len(payload_chunks)

    if needed_slots > len(slots):
        raise ValueError(
            f"payload too large: needs {needed_slots} slots, have {len(slots)} available slots"
        )

    order = prng.build_permutation(prng.derive_seed(passphrase), len(slots))

    # 1. Embed header (always 1 bit per slot for universal detection)
    for i, bit in enumerate(header_bits):
        slot_idx = order[i]
        p_idx, ch = slots[slot_idx]
        px = list(pixels[p_idx])
        px[ch] = lsb.embed_bit(px[ch], bit)
        pixels[p_idx] = tuple(px)

    # 2. Embed payload with chosen bit_depth per slot
    for i, chunk in enumerate(payload_chunks):
        slot_idx = order[len(header_bits) + i]
        p_idx, ch = slots[slot_idx]
        px = list(pixels[p_idx])
        px[ch] = lsb.embed_bits(px[ch], chunk, bit_depth)
        pixels[p_idx] = tuple(px)

    mode = "RGBA" if is_rgba else "RGB"
    out = Image.new(mode, image.size)
    out.putdata(pixels)
    total_bits = len(header_bits) + len(payload_chunks) * bit_depth
    return out, total_bits


def _extract_bytes(passphrase: str, image: Image.Image) -> bytes:
    slots, is_rgba, pixels = _get_slots(image)
    if len(slots) < 64:
        raise ValueError("carrier image too small for stego header")

    order = prng.build_permutation(prng.derive_seed(passphrase), len(slots))

    # Lazy read: extract first 72 bits to check v2 header (or 64 for v1 fallback)
    header_bits = []
    read_limit = min(72, len(slots))
    for i in range(read_limit):
        slot_idx = order[i]
        p_idx, ch = slots[slot_idx]
        header_bits.append(lsb.extract_bit(pixels[p_idx][ch]))

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
    if header_slots + needed_chunks > len(slots):
        raise ValueError("corrupted length in header (exceeds available image slots)")

    chunks: list[int] = []
    for i in range(needed_chunks):
        slot_idx = order[header_slots + i]
        p_idx, ch = slots[slot_idx]
        chunks.append(lsb.extract_bits(pixels[p_idx][ch], bit_depth))

    sealed = chunked_bits_to_bytes(chunks, bit_depth, sealed_len)
    return crypto.open_sealed(passphrase, sealed)


def encode(
    passphrase: str, message: str, carrier_path: str, output_path: str, bit_depth: int = 1
) -> int:
    image = Image.open(carrier_path)
    payload = pack_payload("message.txt", message.encode("utf-8"))
    output_image, bits = _embed_bytes(passphrase, payload, image, bit_depth=bit_depth)
    output_image.save(output_path)
    return bits


def decode(passphrase: str, carrier_path: str) -> str:
    image = Image.open(carrier_path)
    filename, data = unpack_payload(_extract_bytes(passphrase, image))
    return data.decode("utf-8", errors="replace")
