import io

from PIL import Image

import crypto
import prng
import stego

INDEX_BYTES = 5
INDEX_REPEAT = 32
MAX_COPIES = 16
MIN_COPIES = 4
WHATSAPP_QUALITY = 75
WHATSAPP_MAX_DIM = 1280


def preprocess_for_whatsapp(image: Image.Image) -> Image.Image:
    image = image.convert("RGB")
    width, height = image.size
    scale = min(1.0, WHATSAPP_MAX_DIM / max(width, height))
    if scale < 1.0:
        image = image.resize(
            (int(width * scale), int(height * scale)), Image.LANCZOS
        )
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=WHATSAPP_QUALITY, optimize=True)
    buffer.seek(0)
    return Image.open(buffer).convert("RGB")


def _majority_bit(values: list[int]) -> int:
    return 1 if sum(values) > len(values) // 2 else 0


def _index_stream(copies: int, copy_bytes: int) -> bytes:
    index = bytes([copies]) + copy_bytes.to_bytes(4, "big")
    return index * INDEX_REPEAT


def _decode_index(bits: list[int]) -> tuple[int, int]:
    index_bits = INDEX_REPEAT * INDEX_BYTES * 8
    majority = []
    for bit_pos in range(INDEX_BYTES * 8):
        votes = [
            bits[repeat * INDEX_BYTES * 8 + bit_pos]
            for repeat in range(INDEX_REPEAT)
        ]
        majority.append(_majority_bit(votes))

    index_bytes = []
    for byte_pos in range(INDEX_BYTES):
        value = 0
        for i in range(8):
            value |= majority[byte_pos * 8 + i] << i
        index_bytes.append(value)

    copies = index_bytes[0]
    copy_bytes = int.from_bytes(bytes(index_bytes[1:]), "big")
    return copies, copy_bytes


def encode_robust(
    passphrase: str, payload: bytes, image: Image.Image
) -> tuple[Image.Image, int, dict]:
    base = preprocess_for_whatsapp(image)

    sealed = crypto.seal(passphrase, payload)
    full = stego.MAGIC + len(sealed).to_bytes(stego.LENGTH_SIZE, "big") + sealed
    copy_bytes = len(full)

    total_bytes = base.width * base.height * 3 // 8
    available = total_bytes - INDEX_REPEAT * INDEX_BYTES
    copies = min(MAX_COPIES, max(1, available // copy_bytes))
    if copies < MIN_COPIES:
        raise ValueError(
            f"payload too large for WhatsApp mode "
            f"(fits {copies} redundant copies, need at least {MIN_COPIES})"
        )

    stream = _index_stream(copies, copy_bytes) + full * copies
    bits = stego.bytes_to_bits(stream)
    output, embedded = stego._embed_bits(passphrase, bits, base)
    return output, embedded, {"copies": copies, "copy_bytes": copy_bytes}


def decode_robust(passphrase: str, image: Image.Image) -> bytes:
    image = image.convert("RGB")
    total_bytes = image.width * image.height * 3 // 8
    if total_bytes < INDEX_REPEAT * INDEX_BYTES + 1:
        raise ValueError("image too small for robust decode")

    bits = stego._read_bits(passphrase, image)
    copies, copy_bytes = _decode_index(bits)
    if copies < 1 or copy_bytes < stego.HEADER_SIZE or copy_bytes > 1_000_000:
        raise ValueError("robust index is invalid")

    needed = (INDEX_REPEAT * INDEX_BYTES + copies * copy_bytes) * 8
    if needed > len(bits):
        raise ValueError("robust layout exceeds image capacity")

    data_start = INDEX_REPEAT * INDEX_BYTES
    full_bits = []
    for bit_pos in range(copy_bytes * 8):
        votes = [
            bits[(data_start + copy * copy_bytes) * 8 + bit_pos]
            for copy in range(copies)
        ]
        full_bits.append(_majority_bit(votes))

    full = stego.bits_to_bytes(full_bits)
    if full[: stego.MAGIC_LEN] != stego.MAGIC:
        raise ValueError(
            "robust magic not found (wrong passphrase or image is not a carrier)"
        )

    sealed_length = int.from_bytes(
        full[stego.MAGIC_LEN : stego.MAGIC_LEN + stego.LENGTH_SIZE], "big"
    )
    sealed = full[stego.HEADER_SIZE : stego.HEADER_SIZE + sealed_length]
    return crypto.open_sealed(passphrase, sealed)


def simulate_whatsapp(image: Image.Image, quality: int = WHATSAPP_QUALITY) -> Image.Image:
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=quality, optimize=True)
    buffer.seek(0)
    return Image.open(buffer).convert("RGB")