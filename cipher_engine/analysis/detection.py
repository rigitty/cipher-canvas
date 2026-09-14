import base64
import io

import numpy as np
from PIL import Image


def generate_lsb_plane(image: Image.Image) -> str:
    rgb = image.convert("RGB")
    arr = np.array(rgb, dtype=np.uint8)
    plane_data = ((arr[:, :, 0] & 1) | (arr[:, :, 1] & 1) | (arr[:, :, 2] & 1)) * np.uint8(255)
    plane_img = Image.fromarray(plane_data, mode="L")
    width, height = rgb.size
    if max(width, height) > 800:
        scale = 800 / max(width, height)
        plane_img = plane_img.resize(
            (int(width * scale), int(height * scale)), Image.Resampling.NEAREST
        )
    buf = io.BytesIO()
    plane_img.save(buf, "PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"


def analyze_image(image: Image.Image) -> dict:
    rgb = image.convert("RGB")
    arr = np.array(rgb, dtype=np.uint8)
    width, height = rgb.size

    # 1. Pairs-of-Values (PoV) Chi-Square per channel
    channel_stats = []
    for ch in range(3):
        stat = pov_chisq_per_df(arr[:, :, ch])
        channel_stats.append(round(stat, 3))

    avg_stat = sum(channel_stats) / len(channel_stats)

    # 2. Multi-Plane Spatial Autocorrelation (Planes 0, 1, 2, 3)
    plane_corrs = []
    for plane in range(4):
        bits = (arr >> plane) & 1
        match_h = float(np.mean(bits[:, :-1, :] == bits[:, 1:, :]))
        match_v = float(np.mean(bits[:-1, :, :] == bits[1:, :, :]))
        plane_corrs.append((match_h + match_v) / 2.0)

    # Higher-plane noise anomaly (indicates 2..4 LSB steganography)
    p1_anomaly = max(0.0, 1.0 - (max(0.0, plane_corrs[1] - 0.50) / 0.15))
    p2_anomaly = max(0.0, 1.0 - (max(0.0, plane_corrs[2] - 0.50) / 0.20))
    p3_anomaly = max(0.0, 1.0 - (max(0.0, plane_corrs[3] - 0.25) / 0.25))
    multibit_anomaly = float(p1_anomaly * 0.40 + p2_anomaly * 0.35 + p3_anomaly * 0.25)

    # LSB Plane 0 Randomness vs Structure (Photos typically 0.58 - 0.85; Stego ~ 0.500)
    p0_match = plane_corrs[0]
    p0_randomness = float(
        max(0.0, 1.0 - (max(0.0, p0_match - 0.50) / 0.08)) if p0_match > 0.50 else 1.0
    )

    # Assess Chi-Square Equalization:
    unique_colors = len(np.unique(arr.reshape(-1, 3), axis=0))
    is_flat_or_synthetic = unique_colors < 500 or avg_stat > 500

    if is_flat_or_synthetic:
        pov_anomaly = 0.0
    elif 0.85 <= avg_stat <= 1.25:
        pov_anomaly = float(1.0 - abs(avg_stat - 1.0) / 0.25)
    elif (0.70 <= avg_stat < 0.85) or (1.25 < avg_stat <= 1.80):
        pov_anomaly = 0.50
    else:
        pov_anomaly = 0.0

    # Decision tree combining Multi-bit, PoV Equalization, and Plane 0 Noise
    if multibit_anomaly > 0.60:
        risk_score = int(80 + multibit_anomaly * 19)
    elif pov_anomaly > 0.50 and p0_randomness > 0.80:
        risk_score = int(65 + pov_anomaly * 25)
    elif multibit_anomaly > 0.30 or (pov_anomaly > 0.40 and p0_randomness > 0.50):
        risk_score = int(35 + max(multibit_anomaly, pov_anomaly) * 30)
    else:
        risk_score = int(max(2, min(15, p0_randomness * 8 + multibit_anomaly * 10)))

    risk_score = max(2, min(99, risk_score))

    if risk_score >= 70:
        verdict = "HIDDEN PAYLOAD DETECTED"
        color = "#e50914"
        details = "Strong indicators of encrypted data found embedded inside this image's pixel layers."
    elif risk_score >= 35:
        verdict = "SUSPICIOUS PATTERNS"
        color = "#e67e22"
        details = "Minor irregularities detected. Image may contain hidden data or heavy compression."
    else:
        verdict = "CLEAN / NATURAL IMAGE"
        color = "#2ecc71"
        details = (
            "No hidden payload found. Pixel distribution matches standard unmodified photography. "
            "No steganographic signature detected."
        )

    lsb_preview = generate_lsb_plane(image)

    return {
        "risk_score": risk_score,
        "verdict": verdict,
        "color": color,
        "details": details,
        "dimensions": f"{image.width} \u00d7 {image.height}",
        "total_pixels": f"{image.width * image.height:,}",
        "unique_colors": f"{unique_colors:,}",
        "chi_square": {
            "red": channel_stats[0],
            "green": channel_stats[1],
            "blue": channel_stats[2],
            "average": round(avg_stat, 3),
        },
        "chi_square_per_df": {
            "red": channel_stats[0],
            "green": channel_stats[1],
            "blue": channel_stats[2],
            "average": round(avg_stat, 3),
        },
        "bit_planes": [
            {
                "plane": "LSB (Plane 0)",
                "correlation": round(plane_corrs[0], 4),
                "status": "Random" if plane_corrs[0] < 0.53 else "Natural",
            },
            {
                "plane": "Plane 1",
                "correlation": round(plane_corrs[1], 4),
                "status": "Random" if plane_corrs[1] < 0.58 else "Natural",
            },
            {
                "plane": "Plane 2",
                "correlation": round(plane_corrs[2], 4),
                "status": "Random" if plane_corrs[2] < 0.70 else "Natural",
            },
            {
                "plane": "Plane 3",
                "correlation": round(plane_corrs[3], 4),
                "status": "Random" if plane_corrs[3] < 0.85 else "Natural",
            },
        ],
        "metrics": {
            "p0_randomness": f"{round(p0_randomness * 100, 1)}%",
            "multibit_anomaly": f"{round(multibit_anomaly * 100, 1)}%",
            "pov_anomaly": f"{round(pov_anomaly * 100, 1)}%",
        },
        "lsb_preview": lsb_preview,
    }


def pov_chisq_per_df(channel_arr: np.ndarray) -> float:
    flat = channel_arr.reshape(-1)
    histogram = np.bincount(flat, minlength=256)
    evens = histogram[0::2].astype(np.float64)
    odds = histogram[1::2].astype(np.float64)
    pair_sums = evens + odds
    nonzero = pair_sums > 0
    if not np.any(nonzero):
        return 0.0
    expected = pair_sums[nonzero] / 2.0
    stat = np.sum((evens[nonzero] - expected) ** 2 / expected) + np.sum(
        (odds[nonzero] - expected) ** 2 / expected
    )
    df = np.sum(nonzero)
    return float(stat / df) if df > 0 else 0.0


def pov_profile(path: str, channel: int = 0, step: int = 5) -> list[tuple[int, float]]:
    image = Image.open(path).convert("RGB")
    arr = np.array(image, dtype=np.uint8)[:, :, channel]
    flat = arr.reshape(-1)
    total = len(flat)
    profile = []
    for pct in range(step, 101, step):
        count = int(total * pct / 100)
        profile.append((pct, pov_chisq_per_df(flat[:count])))
    return profile


def deviation_from_baseline(stego_path: str, clean_path: str, channel: int = 0) -> float:
    clean = [v for _, v in pov_profile(clean_path, channel)]
    stego_profile = [v for _, v in pov_profile(stego_path, channel)]
    return sum(abs(a - b) for a, b in zip(clean, stego_profile))


def change_locations(clean_path: str, stego_path: str, row_bins: int = 10) -> list[int]:
    clean = Image.open(clean_path).convert("RGB")
    stego_image = Image.open(stego_path).convert("RGB")
    clean_arr = np.array(clean, dtype=np.uint8)
    stego_arr = np.array(stego_image, dtype=np.uint8)
    diff_mask = np.any(clean_arr != stego_arr, axis=2)
    height, width = diff_mask.shape
    bins = [0] * row_bins
    for row in range(height):
        changes = int(np.sum(diff_mask[row, :]))
        if changes > 0:
            bin_index = min(row * row_bins // height, row_bins - 1)
            bins[bin_index] += changes
    return bins


def report(clean_path: str, stego_path: str, label: str, channel: int = 0) -> None:
    dev = deviation_from_baseline(stego_path, clean_path, channel)
    bins = change_locations(clean_path, stego_path)
    total_changes = sum(bins)
    print(f"--- {label} ---")
    print(f"  PoV deviation vs clean   : {dev:.3f}")
    print(f"  changed pixels           : {total_changes}")
    print(f"  change distribution (row): {bins}")
    print()
