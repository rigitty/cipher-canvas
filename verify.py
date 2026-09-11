from PIL import Image

import capacity
import stego

PASSPHRASE = "correct horse battery staple"


def test_hide_image() -> None:
    secret_image = Image.new("RGB", (24, 24), (200, 30, 60))
    buffer = __import__("io").BytesIO()
    secret_image.save(buffer, format="PNG")
    secret_bytes = buffer.getvalue()

    carrier = Image.open("samples/sample.png")
    output, _ = stego._embed_bytes(
        PASSPHRASE,
        stego.pack_payload("secret-photo.png", secret_bytes),
        carrier,
    )

    extracted = stego._extract_bytes(PASSPHRASE, output)
    filename, data = stego.unpack_payload(extracted)
    assert filename == "secret-photo.png", f"filename mismatch: {filename}"
    assert data == secret_bytes, "binary round-trip mismatch"
    print(f"PASS hide image: {filename} ({len(data)} bytes) inside carrier")


def expect_roundtrip(message: str, carrier: str = "samples/sample.png") -> None:
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
    width, height = Image.open("samples/sample.png").size
    limit = capacity.max_plaintext_bytes(
        width, height, filename_length=len("message.txt")
    )
    expect_roundtrip("a" * limit)


def test_too_large() -> None:
    width, height = Image.open("samples/sample.png").size
    limit = capacity.max_plaintext_bytes(
        width, height, filename_length=len("message.txt")
    )

    def encode_oversized():
        stego.encode(PASSPHRASE, "a" * (limit + 1), "samples/sample.png", "_never.png")

    expect_error("oversized message rejected", encode_oversized)


def test_wrong_passphrase() -> None:
    stego.encode(PASSPHRASE, "hello", "samples/sample.png", "_verify_out.png")

    def decode_wrong():
        stego.decode("wrong passphrase", "_verify_out.png")

    expect_error("wrong passphrase rejected", decode_wrong)


def test_non_carrier() -> None:
    expect_error(
        "non-carrier image rejected", lambda: stego.decode(PASSPHRASE, "samples/sample.png")
    )


def test_tampered_carrier() -> None:
    stego.encode(PASSPHRASE, "integrity matters", "samples/sample.png", "_verify_out.png")
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


def test_bit_depths() -> None:
    for b in [1, 2, 3, 4]:
        width, height = Image.open("samples/sample.png").size
        limit = capacity.max_plaintext_bytes(
            width, height, filename_length=len("message.txt"), bit_depth=b
        )
        msg = f"Bit depth {b} test: " + ("x" * min(limit, 200))
        stego.encode(PASSPHRASE, msg, "samples/sample.png", "_verify_out.png", bit_depth=b)
        recovered = stego.decode(PASSPHRASE, "_verify_out.png")
        assert recovered == msg, f"bit_depth {b} roundtrip failed"
        print(f"PASS variable bit depth {b}/4: capacity = {limit} bytes")


def test_alpha_preservation() -> None:
    rgba = Image.new("RGBA", (100, 100), (40, 80, 120, 255))
    # Make top 20 rows completely transparent (alpha = 0)
    for y in range(20):
        for x in range(100):
            rgba.putpixel((x, y), (0, 0, 0, 0))
    rgba.save("_verify_rgba.png")

    msg = "Alpha transparency preserved perfectly!"
    stego.encode(PASSPHRASE, msg, "_verify_rgba.png", "_verify_rgba_out.png")
    out = Image.open("_verify_rgba_out.png")
    assert out.mode == "RGBA", "RGBA mode was not preserved"
    assert out.getpixel((10, 10)) == (0, 0, 0, 0), "Transparent pixels were modified"
    recovered = stego.decode(PASSPHRASE, "_verify_rgba_out.png")
    assert recovered == msg, "RGBA roundtrip failed"
    print("PASS alpha preservation: transparency untouched and preserved in RGBA PNG")


def test_robust_jpeg_resilience() -> None:
    import io
    import robust

    carrier_path = "samples/logo.jpg"
    out_path = "_verify_robust_out.png"
    secret_msg = "Secret coordinates: 41.0082° N, 28.9784° E. WhatsApp resilience verified."

    robust.encode(PASSPHRASE, secret_msg, carrier_path, out_path)

    # 1. Direct decode (lossless)
    recovered_lossless = robust.decode(PASSPHRASE, out_path)
    assert recovered_lossless == secret_msg, "Robust lossless decode failed"

    # 2. Simulated WhatsApp / JPEG lossy compression (Quality 70)
    with Image.open(out_path) as im:
        jpeg_buf = io.BytesIO()
        im.save(jpeg_buf, format="JPEG", quality=70)
        jpeg_buf.seek(0)
        jpeg_path = "_verify_robust_q70.jpg"
        with open(jpeg_path, "wb") as f:
            f.write(jpeg_buf.getvalue())

    recovered_lossy = robust.decode(PASSPHRASE, jpeg_path)
    assert recovered_lossy == secret_msg, "Robust lossy JPEG Q70 decode failed"
    print("PASS robust mode: survives JPEG Q70 / WhatsApp lossy compression roundtrip")


def cleanup_temp_files() -> None:
    import glob
    import os
    for pattern in ["_verify_*.png", "_verify_*.jpg", "_tiny.png", "_never.png", "_out.png"]:
        for f in glob.glob(pattern):
            try:
                os.remove(f)
            except OSError:
                pass


if __name__ == "__main__":
    try:
        test_unicode()
        test_empty_message()
        test_exact_capacity()
        test_too_large()
        test_wrong_passphrase()
        test_non_carrier()
        test_tampered_carrier()
        test_tiny_image()
        test_hide_image()
        test_bit_depths()
        test_alpha_preservation()
        test_robust_jpeg_resilience()
        print("ALL EDGE-CASE TESTS PASSED")
    finally:
        cleanup_temp_files()
