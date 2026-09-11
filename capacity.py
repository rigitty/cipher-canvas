import math
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
    if max(width, height) > 1280:
        scale = 1280 / max(width, height)
        width = max(8, (int(width * scale) // 8) * 8)
        height = max(8, (int(height * scale) // 8) * 8)
    else:
        width = (width // 8) * 8
        height = (height // 8) * 8
    total_blocks = (width // 8) * (height // 8)
    avail = total_blocks - 112
    if avail <= 0:
        return 0
    max_ecc_bytes = avail // 8
    low, high, ans = 0, max_ecc_bytes, 0
    while low <= high:
        mid = (low + high) // 2
        raw_len = mid + 52  # 44 crypto seal + 4 magic + 4 len
        chunks = math.ceil(raw_len / 223) if raw_len > 0 else 1
        ecc_len = raw_len + chunks * 32
        if ecc_len * 8 <= avail:
            ans = mid
            low = mid + 1
        else:
            high = mid - 1
    return ans
