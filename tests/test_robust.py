import io

import pytest
from PIL import Image

from cipher_engine.core import robust


def test_robust_roundtrip(large_carrier: Image.Image, passphrase: str):
    message = "Robust DCT + Reed-Solomon roundtrip verification."
    stego_img = robust.encode_image(passphrase, message, large_carrier)

    recovered = robust.decode_image(passphrase, stego_img)
    assert recovered == message


def test_robust_survives_jpeg_compression(large_carrier: Image.Image, passphrase: str):
    message = "JPEG Q70 WhatsApp resilient secret message!"
    stego_img = robust.encode_image(passphrase, message, large_carrier)

    # Compress to lossy JPEG Q70 in-memory
    buf = io.BytesIO()
    stego_img.save(buf, "JPEG", quality=70)
    buf.seek(0)
    compressed_img = Image.open(buf)

    # Recover through JPEG lossy artifacts
    recovered = robust.decode_image(passphrase, compressed_img)
    assert recovered == message


def test_robust_wrong_passphrase_rejected(large_carrier: Image.Image, passphrase: str):
    stego_img = robust.encode_image(passphrase, "Hidden robust message", large_carrier)
    with pytest.raises(ValueError):
        robust.decode_image("incorrect-passphrase", stego_img)
