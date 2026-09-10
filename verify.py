from PIL import Image

import capacity
import stego

PASSPHRASE = "correct horse battery staple"


def expect_roundtrip(message: str, carrier: str = "sample.png") -> None:
    stego.encode(PASSPHRASE, message, carrier, "_verify_out.png")
    recovered = stego.decode(PASSPHRASE, "_verify_out.png")
    assert recovered == message, f"round-trip mismatch: {recovered!r} != {message!r}"
    print(f"PASS round-trip {len(message):>5} chars: {message[:32]!r}")


def expect_error(description: str, func) -> None:
    try:
        func()
    except Exception as exc:
        print(f"PASS {description}: {type(exc).__name__}: {exc}")
    else:
        raise AssertionError(f"expected error but none raised for: {description}")


def test_unicode() -> None:
    expect_roundtrip("gizli mesaj: Türkçe karakterler üğışçö — pixel 255")


def test_empty_message() -> None:
    expect_roundtrip("")


def test_exact_capacity() -> None:
    width, height = Image.open("sample.png").size
    limit = capacity.max_plaintext_bytes(width, height)
    expect_roundtrip("a" * limit)


def test_too_large() -> None:
    width, height = Image.open("sample.png").size
    limit = capacity.max_plaintext_bytes(width, height)

    def encode_oversized():
        stego.encode(PASSPHRASE, "a" * (limit + 1), "sample.png", "_never.png")

    expect_error("oversized message rejected", encode_oversized)


def test_wrong_passphrase() -> None:
    stego.encode(PASSPHRASE, "hello", "sample.png", "_verify_out.png")

    def decode_wrong():
        stego.decode("wrong passphrase", "_verify_out.png")

    expect_error("wrong passphrase rejected", decode_wrong)


def test_non_carrier() -> None:
    expect_error(
        "non-carrier image rejected", lambda: stego.decode(PASSPHRASE, "sample.png")
    )


def test_tampered_carrier() -> None:
    stego.encode(PASSPHRASE, "integrity matters", "sample.png", "_verify_out.png")
    image = Image.open("_verify_out.png").convert("RGB")
    pixels = list(image.get_flattened_data())
    slot_count = len(pixels) * 3

    payload_bits = len(
        stego.bytes_to_bits(
            stego.MAGIC
            + (0).to_bytes(4, "big")
            + b"x" * 25
        )
    )
    order = stego.prng.build_permutation(stego.prng.derive_seed(PASSPHRASE), slot_count)
    used_slot = order[payload_bits - 1]
    pixel_index = used_slot // 3
    channel = used_slot % 3

    r, g, b = pixels[pixel_index]
    if channel == 0:
        pixels[pixel_index] = (r ^ 0x01, g, b)
    elif channel == 1:
        pixels[pixel_index] = (r, g ^ 0x01, b)
    else:
        pixels[pixel_index] = (r, g, b ^ 0x01)
    image.putdata(pixels)
    image.save("_verify_tampered.png")

    expect_error(
        "tampered carrier detected (GCM tag)",
        lambda: stego.decode(PASSPHRASE, "_verify_tampered.png"),
    )


def test_tiny_image() -> None:
    tiny = Image.new("RGB", (1, 1), (255, 0, 0))
    tiny.save("_tiny.png")

    def encode_tiny():
        stego.encode(PASSPHRASE, "x", "_tiny.png", "_never.png")

    expect_error("tiny image (no room for header) rejected", encode_tiny)


if __name__ == "__main__":
    test_unicode()
    test_empty_message()
    test_exact_capacity()
    test_too_large()
    test_wrong_passphrase()
    test_non_carrier()
    test_tampered_carrier()
    test_tiny_image()
    print("ALL EDGE-CASE TESTS PASSED")
