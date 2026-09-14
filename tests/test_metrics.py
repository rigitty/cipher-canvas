import numpy as np
from PIL import Image

from cipher_engine.analysis import metrics


def test_psnr_identical_images():
    arr = np.zeros((100, 100, 3), dtype=np.uint8)
    assert metrics.compute_psnr(arr, arr) == 100.0


def test_ssim_identical_images():
    arr = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
    ssim = metrics.compute_ssim(arr, arr)
    assert round(ssim, 4) == 1.0


def test_ber_zero_and_half():
    data = b"abcdefgh"
    assert metrics.compute_ber(data, data) == 0.0

    # Inverted bytes -> BER is 1.0
    inverted = bytes([b ^ 0xFF for b in data])
    assert metrics.compute_ber(data, inverted) == 1.0


def test_evaluate_quality_report(sample_carrier_rgb: Image.Image):
    stego = sample_carrier_rgb.copy()
    # Modify 10 pixels by 1 LSB
    for i in range(10):
        r, g, b = stego.getpixel((i, i))
        stego.putpixel((i, i), (r ^ 1, g, b))

    report = metrics.evaluate_quality(sample_carrier_rgb, stego, bits_written=80)
    assert report["psnr_db"] > 60.0
    assert report["ssim"] > 0.999
    assert report["changed_pixels"] == 10
    assert report["quality_tier"] == "IMPERCEPTIBLE"
