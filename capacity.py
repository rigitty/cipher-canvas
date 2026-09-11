import stego

HEADER_BYTES = 9
AES_OVERHEAD = 44  # salt(16) + nonce(12) + GCM tag(16)


def max_plaintext_bytes(
    width: int, height: int, channels: int = 3, filename_length: int = 0, bit_depth: int = 1
) -> int:
    bit_depth = max(1, min(4, int(bit_depth)))
    total_slots = width * height * channels
    available_slots = max(0, total_slots - 72)
    payload_bits = available_slots * bit_depth
    payload_bytes = payload_bits // 8
    envelope = filename_length + 1
    return max(0, payload_bytes - AES_OVERHEAD - envelope)


def max_payload_bits(width: int, height: int, channels: int = 3, bit_depth: int = 1) -> int:
    bit_depth = max(1, min(4, int(bit_depth)))
    total_slots = width * height * channels
    available_slots = max(0, total_slots - 72)
    return max(0, available_slots * bit_depth - AES_OVERHEAD * 8)


def max_robust_capacity_bytes(width: int, height: int) -> int:
    bh = height // 8
    bw = width // 8
    total_blocks = bh * bw
    avail_blocks = total_blocks - 112
    if avail_blocks <= 0:
        return 0
    max_ecc_bytes = avail_blocks // 8
    overhead = 32 + 4 + 4 + 16 + 12 + 16
    return max(0, max_ecc_bytes - overhead)
