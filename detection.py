from PIL import Image
from scipy.stats import chi2

import stego


def pov_chisq_per_df(pixels: list, channel: int, count: int) -> float:
    histogram = [0] * 256
    for pixel in pixels[:count]:
        histogram[pixel[channel]] += 1
    stat = 0.0
    degrees_of_freedom = 0
    for k in range(0, 256, 2):
        pair_sum = histogram[k] + histogram[k + 1]
        if pair_sum == 0:
            continue
        expected = pair_sum / 2
        stat += (histogram[k] - expected) ** 2 / expected
        stat += (histogram[k + 1] - expected) ** 2 / expected
        degrees_of_freedom += 1
    return stat / degrees_of_freedom


def pov_profile(path: str, channel: int = 0, step: int = 5) -> list[tuple[int, float]]:
    image = Image.open(path).convert("RGB")
    pixels = list(image.get_flattened_data())
    total = len(pixels)
    profile = []
    for pct in range(step, 101, step):
        count = int(total * pct / 100)
        profile.append((pct, pov_chisq_per_df(pixels, channel, count)))
    return profile


def deviation_from_baseline(
    stego_path: str, clean_path: str, channel: int = 0
) -> float:
    clean = [v for _, v in pov_profile(clean_path, channel)]
    stego_profile = [v for _, v in pov_profile(stego_path, channel)]
    return sum(abs(a - b) for a, b in zip(clean, stego_profile))


def change_locations(clean_path: str, stego_path: str, row_bins: int = 10) -> list[int]:
    clean = Image.open(clean_path).convert("RGB")
    stego_image = Image.open(stego_path).convert("RGB")
    width, height = clean.size
    bins = [0] * row_bins
    clean_pixels = list(clean.get_flattened_data())
    stego_pixels = list(stego_image.get_flattened_data())
    for index, (a, b) in enumerate(zip(clean_pixels, stego_pixels)):
        if a != b:
            row = index // width
            bin_index = min(row * row_bins // height, row_bins - 1)
            bins[bin_index] += 1
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


def demo() -> None:
    import random
    import math

    def make_smooth_carrier(path: str, w: int = 300, h: int = 200) -> None:
        rng = random.Random(7)
        image = Image.new("RGB", (w, h))
        pixels = image.load()
        for y in range(h):
            for x in range(w):
                r = 128 + 55 * math.sin(x * 0.20) * math.cos(y * 0.13)
                g = 128 + 40 * math.cos(x * 0.11) * math.sin(y * 0.09)
                b = 128 + 45 * math.sin((x + y) * 0.04)
                pixels[x, y] = (
                    max(0, min(255, int(r + rng.gauss(0, 2.5)))),
                    max(0, min(255, int(g + rng.gauss(0, 2.5)))),
                    max(0, min(255, int(b + rng.gauss(0, 2.5)))),
                )
        image.save(path)

    def embed_sequential(image: Image.Image, bits: list[int]) -> Image.Image:
        pixels = list(image.get_flattened_data())
        for i, bit in enumerate(bits):
            pixel_index = i // 3
            channel = i % 3
            value = list(pixels[pixel_index])
            value[channel] = stego.lsb.embed_bit(value[channel], bit)
            pixels[pixel_index] = tuple(value)
        image.putdata(pixels)
        return image

    make_smooth_carrier("noisy.png")

    message = ("x" * 800) * 5
    stego.encode("pass", message, "noisy.png", "carrier_prng.png")

    seq_bits = stego.bytes_to_bits(
        stego.MAGIC + (4000).to_bytes(4, "big") + b"x" * 4000
    )
    sequential = Image.open("noisy.png").convert("RGB")
    embed_sequential(sequential, seq_bits)
    sequential.save("carrier_seq.png")

    report("noisy.png", "noisy.png", "clean (no embedding)")
    report("noisy.png", "carrier_seq.png", "sequential embedding")
    report("noisy.png", "carrier_prng.png", "PRNG distributed embedding")


if __name__ == "__main__":
    demo()
