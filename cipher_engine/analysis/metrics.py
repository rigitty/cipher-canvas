import math
from typing import Any, Dict
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter


def compute_mse(img1: np.ndarray, img2: np.ndarray) -> float:
    """Computes Mean Squared Error (MSE) between two RGB images."""
    return float(np.mean((img1.astype(np.float64) - img2.astype(np.float64)) ** 2))


def compute_psnr(img1: np.ndarray, img2: np.ndarray) -> float:
    """Computes Peak Signal-to-Noise Ratio (PSNR) in decibels (dB).

    > 50 dB indicates visual imperceptibility (research benchmark).
    """
    mse = compute_mse(img1, img2)
    if mse == 0.0:
        return 100.0  # Identical images
    return float(10.0 * np.log10((255.0**2) / mse))


def compute_ssim(img1: np.ndarray, img2: np.ndarray) -> float:
    """Computes Structural Similarity Index Measure (SSIM) according to Wang et al. (2004)."""
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2

    arr1 = img1.astype(np.float64)
    arr2 = img2.astype(np.float64)

    if arr1.ndim == 3:
        channel_ssims = []
        for ch in range(min(arr1.shape[2], arr2.shape[2])):
            channel_ssims.append(compute_ssim(arr1[:, :, ch], arr2[:, :, ch]))
        return float(np.mean(channel_ssims)) if channel_ssims else 1.0

    mu1 = gaussian_filter(arr1, 1.5)
    mu2 = gaussian_filter(arr2, 1.5)
    mu1_sq = mu1**2
    mu2_sq = mu2**2
    mu1_mu2 = mu1 * mu2

    sigma1_sq = gaussian_filter(arr1**2, 1.5) - mu1_sq
    sigma2_sq = gaussian_filter(arr2**2, 1.5) - mu2_sq
    sigma12 = gaussian_filter(arr1 * arr2, 1.5) - mu1_mu2

    num = (2.0 * mu1_mu2 + c1) * (2.0 * sigma12 + c2)
    den = (mu1_sq + mu2_sq + c1) * (sigma1_sq + sigma2_sq + c2)

    return float(np.mean(num / den))


def compute_entropy(channel: np.ndarray) -> float:
    """Computes Shannon entropy for an 8-bit image channel (0.0 to 8.0 bits)."""
    flat = channel.reshape(-1)
    counts = np.bincount(flat, minlength=256)
    probs = counts[counts > 0] / float(len(flat))
    return float(-np.sum(probs * np.log2(probs)))


def compute_bpp(bits_written: int, width: int, height: int) -> float:
    """Computes Bits Per Pixel (bpp) embedding rate."""
    total_pixels = width * height
    return float(bits_written / total_pixels) if total_pixels > 0 else 0.0


def compute_ber(original_bytes: bytes, received_bytes: bytes) -> float:
    """Computes Bit Error Rate (BER) between original and received payload bytes."""
    if not original_bytes and not received_bytes:
        return 0.0
    min_len = min(len(original_bytes), len(received_bytes))
    max_len = max(len(original_bytes), len(received_bytes))

    bit_errors = 0
    for i in range(min_len):
        xor = original_bytes[i] ^ received_bytes[i]
        bit_errors += bin(xor).count("1")

    # Extra bytes are completely mismatched (8 bit errors each)
    bit_errors += (max_len - min_len) * 8
    total_bits = max_len * 8
    return float(bit_errors / total_bits) if total_bits > 0 else 0.0


def evaluate_quality(
    carrier: Image.Image,
    stego: Image.Image,
    bits_written: int = 0,
) -> Dict[str, Any]:
    """Generates a comprehensive scientific quality report comparing carrier vs stego image."""
    c_rgb = carrier.convert("RGB")
    s_rgb = stego.convert("RGB")

    w, h = min(c_rgb.width, s_rgb.width), min(c_rgb.height, s_rgb.height)
    if c_rgb.size != (w, h):
        c_rgb = c_rgb.crop((0, 0, w, h))
    if s_rgb.size != (w, h):
        s_rgb = s_rgb.crop((0, 0, w, h))

    c_arr = np.array(c_rgb, dtype=np.uint8)
    s_arr = np.array(s_rgb, dtype=np.uint8)

    mse = compute_mse(c_arr, s_arr)
    psnr = compute_psnr(c_arr, s_arr)
    ssim = compute_ssim(c_arr, s_arr)
    bpp = compute_bpp(bits_written, w, h)

    diff_mask = np.any(c_arr != s_arr, axis=2)
    changed_pixels = int(np.sum(diff_mask))
    total_pixels = w * h
    pct_changed = (changed_pixels / total_pixels) * 100.0 if total_pixels > 0 else 0.0

    entropies = {
        "carrier": [round(compute_entropy(c_arr[:, :, ch]), 3) for ch in range(3)],
        "stego": [round(compute_entropy(s_arr[:, :, ch]), 3) for ch in range(3)],
    }

    if psnr >= 55.0 and ssim >= 0.9995:
        tier = "IMPERCEPTIBLE"
        tier_desc = "Near-zero distortion. Undetectable to human eyes and standard vision models."
    elif psnr >= 45.0 and ssim >= 0.990:
        tier = "EXCELLENT"
        tier_desc = "Extremely high fidelity. Minimal noise in lower bitplanes."
    elif psnr >= 35.0:
        tier = "ACCEPTABLE"
        tier_desc = "Minor visible noise under magnification or in flat colour regions."
    else:
        tier = "DEGRADED"
        tier_desc = "Noticeable compression or modification artifacts."

    return {
        "psnr_db": round(psnr, 2),
        "ssim": round(ssim, 5),
        "mse": round(mse, 4),
        "bpp": round(bpp, 4),
        "changed_pixels": changed_pixels,
        "total_pixels": total_pixels,
        "changed_percentage": f"{pct_changed:.2f}%",
        "quality_tier": tier,
        "quality_description": tier_desc,
        "channel_entropies": {
            "carrier_rgb": entropies["carrier"],
            "stego_rgb": entropies["stego"],
        },
    }
