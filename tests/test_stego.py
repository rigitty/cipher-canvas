import io
import pytest
import numpy as np
from PIL import Image

from cipher_engine.core import capacity, stego


def test_roundtrip_unicode(sample_carrier_rgb: Image.Image, passphrase: str):
    message = "Gizli Mesaj: Türkçe karakterler çğıöşü — Pixel 255"
    payload = stego.pack_payload("msg.txt", message.encode("utf-8"))

    stego_img, bits = stego._embed_bytes(passphrase, payload, sample_carrier_rgb, bit_depth=1)
    assert bits > 0

    extracted = stego._extract_bytes(passphrase, stego_img)
    filename, data = stego.unpack_payload(extracted)
    assert filename == "msg.txt"
    assert data.decode("utf-8") == message


def test_roundtrip_empty_message(sample_carrier_rgb: Image.Image, passphrase: str):
    payload = stego.pack_payload("empty.txt", b"")
    stego_img, _ = stego._embed_bytes(passphrase, payload, sample_carrier_rgb, bit_depth=1)
    extracted = stego._extract_bytes(passphrase, stego_img)
    filename, data = stego.unpack_payload(extracted)
    assert filename == "empty.txt"
    assert data == b""


def test_roundtrip_binary_file(sample_carrier_rgb: Image.Image, passphrase: str):
    secret_bytes = bytes([i % 256 for i in range(500)])
    payload = stego.pack_payload("firmware.bin", secret_bytes)

    stego_img, _ = stego._embed_bytes(passphrase, payload, sample_carrier_rgb, bit_depth=2)
    extracted = stego._extract_bytes(passphrase, stego_img)
    filename, data = stego.unpack_payload(extracted)
    assert filename == "firmware.bin"
    assert data == secret_bytes


@pytest.mark.parametrize("bit_depth", [1, 2, 3, 4])
def test_variable_bit_depths(sample_carrier_rgb: Image.Image, passphrase: str, bit_depth: int):
    message = f"Bit depth {bit_depth} verification payload" * 10
    payload = stego.pack_payload("test.txt", message.encode("utf-8"))

    stego_img, bits = stego._embed_bytes(passphrase, payload, sample_carrier_rgb, bit_depth=bit_depth)
    extracted = stego._extract_bytes(passphrase, stego_img)
    _, data = stego.unpack_payload(extracted)
    assert data.decode("utf-8") == message


def test_alpha_channel_preservation(sample_carrier_rgba: Image.Image, passphrase: str):
    orig_alpha = np.array(sample_carrier_rgba)[:, :, 3].copy()
    payload = stego.pack_payload("secret.txt", b"Transparent pixel preservation test")

    stego_img, _ = stego._embed_bytes(passphrase, payload, sample_carrier_rgba, bit_depth=1)
    new_alpha = np.array(stego_img)[:, :, 3]

    # Alpha channel must remain completely untouched
    np.testing.assert_array_equal(orig_alpha, new_alpha)

    # Decode must succeed
    extracted = stego._extract_bytes(passphrase, stego_img)
    _, data = stego.unpack_payload(extracted)
    assert data == b"Transparent pixel preservation test"


def test_capacity_overflow_rejected(sample_carrier_rgb: Image.Image, passphrase: str):
    w, h = sample_carrier_rgb.size
    max_bytes = capacity.max_plaintext_bytes(w, h, bit_depth=1)

    # 1 byte over capacity should raise ValueError
    oversized_data = b"x" * (max_bytes + 10)
    payload = stego.pack_payload("overflow.bin", oversized_data, compress=False)

    with pytest.raises(ValueError, match="payload too large"):
        stego._embed_bytes(passphrase, payload, sample_carrier_rgb, bit_depth=1)


def test_zstd_compression_benefit():
    repetitive_text = b"test123test123" * 500  # 7,000 bytes
    packed_uncompressed = stego.pack_payload("rep.txt", repetitive_text, compress=False)
    packed_compressed = stego.pack_payload("rep.txt", repetitive_text, compress=True)

    assert len(packed_compressed) < len(packed_uncompressed) / 10
    # Decompression restores original bytes exactly
    fname, recovered = stego.unpack_payload(packed_compressed)
    assert fname == "rep.txt"
    assert recovered == repetitive_text
