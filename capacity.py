import stego

HEADER_BYTES = stego.HEADER_SIZE
AES_OVERHEAD = 44  # salt(16) + nonce(12) + GCM tag(16)


def max_plaintext_bytes(width: int, height: int, channels: int = 3) -> int:
    slots = width * height * channels
    payload_bytes = slots // 8
    return max(0, payload_bytes - HEADER_BYTES - AES_OVERHEAD)


def max_payload_bits(width: int, height: int, channels: int = 3) -> int:
    return (width * height * channels) - (HEADER_BYTES + AES_OVERHEAD) * 8


def demo() -> None:
    for (w, h) in [(100, 100), (300, 200), (1920, 1080)]:
        print(
            f"{w}x{h}: {max_plaintext_bytes(w, h)} plaintext bytes "
            f"(= {max_plaintext_bytes(w, h) // 1024} KiB, {max_payload_bits(w, h)} bits)"
        )


if __name__ == "__main__":
    demo()
