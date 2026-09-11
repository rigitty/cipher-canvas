import numpy as np
from PIL import Image
from scipy.fftpack import dct, idct
import reedsolo

import crypto
import prng

MAGIC_ROBUST = b"ROBU"
HEADER_BITS = 16
HEADER_REP = 7
HEADER_BLOCKS = HEADER_BITS * HEADER_REP  # 112 blocks
RS_PARITY_BYTES = 32
DELTA_MODULATION = 45.0


def dct2(a: np.ndarray) -> np.ndarray:
    return dct(dct(a.T, norm="ortho").T, norm="ortho")


def idct2(a: np.ndarray) -> np.ndarray:
    return idct(idct(a.T, norm="ortho").T, norm="ortho")


def bytes_to_bits(data: bytes) -> list[int]:
    bits = []
    for b in data:
        for i in range(7, -1, -1):
            bits.append((b >> i) & 1)
    return bits


def bits_to_bytes(bits: list[int]) -> bytes:
    out = bytearray()
    for i in range(0, len(bits) - 7, 8):
        byte = 0
        for bit in bits[i : i + 8]:
            byte = (byte << 1) | bit
        out.append(byte)
    return bytes(out)


def max_robust_capacity_bytes(width: int, height: int) -> int:
    bh = height // 8
    bw = width // 8
    total_blocks = bh * bw
    avail_blocks = total_blocks - HEADER_BLOCKS
    if avail_blocks <= 0:
        return 0
    max_ecc_bytes = avail_blocks // 8
    overhead = RS_PARITY_BYTES + 4 + 4 + 16 + 12 + 16
    return max(0, max_ecc_bytes - overhead)


def encode(passphrase: str, message: str, carrier_path: str, output_path: str) -> None:
    sealed = crypto.seal(passphrase, message.encode("utf-8"))
    raw_packet = MAGIC_ROBUST + len(sealed).to_bytes(4, "big") + sealed

    rs = reedsolo.RSCodec(RS_PARITY_BYTES)
    ecc_packet = rs.encode(raw_packet)
    ecc_len = len(ecc_packet)

    hdr_bytes = ecc_len.to_bytes(2, "big")
    hdr_bits = bytes_to_bits(hdr_bytes)
    hdr_rep_bits = []
    for b in hdr_bits:
        hdr_rep_bits.extend([b] * HEADER_REP)

    payload_bits = bytes_to_bits(ecc_packet)

    with Image.open(carrier_path) as im:
        rgb_img = im.convert("RGB")
        ycbcr = rgb_img.convert("YCbCr")

    y, cb, cr = ycbcr.split()
    y_arr = np.array(y, dtype=np.float32)
    h, w = y_arr.shape
    bh, bw = h // 8, w // 8
    total_blocks = bh * bw

    avail_payload_blocks = total_blocks - len(hdr_rep_bits)
    if avail_payload_blocks < len(payload_bits):
        raise ValueError(
            f"Carrier image too small for robust embedding. Needs {len(hdr_rep_bits)+len(payload_bits)} 8x8 blocks, have {total_blocks} available."
        )

    rep = max(1, avail_payload_blocks // len(payload_bits))
    if rep % 2 == 0:
        rep -= 1
    rep = min(rep, 7)

    seed = prng.derive_seed(passphrase + "_robust")
    order = prng.build_permutation(seed, total_blocks)

    for i, bit in enumerate(hdr_rep_bits):
        bidx = order[i]
        by, bx = bidx // bw, bidx % bw
        block = y_arr[by * 8 : (by + 1) * 8, bx * 8 : (bx + 1) * 8]
        d = dct2(block)
        avg = (d[3, 2] + d[2, 3]) / 2.0
        if bit == 1:
            d[3, 2] = avg + DELTA_MODULATION / 2.0
            d[2, 3] = avg - DELTA_MODULATION / 2.0
        else:
            d[3, 2] = avg - DELTA_MODULATION / 2.0
            d[2, 3] = avg + DELTA_MODULATION / 2.0
        y_arr[by * 8 : (by + 1) * 8, bx * 8 : (bx + 1) * 8] = idct2(d)

    payload_start_slot = len(hdr_rep_bits)
    for i, bit in enumerate(payload_bits):
        for r in range(rep):
            slot = payload_start_slot + i * rep + r
            if slot >= total_blocks:
                break
            bidx = order[slot]
            by, bx = bidx // bw, bidx % bw
            block = y_arr[by * 8 : (by + 1) * 8, bx * 8 : (bx + 1) * 8]
            d = dct2(block)
            avg = (d[3, 2] + d[2, 3]) / 2.0
            if bit == 1:
                d[3, 2] = avg + DELTA_MODULATION / 2.0
                d[2, 3] = avg - DELTA_MODULATION / 2.0
            else:
                d[3, 2] = avg - DELTA_MODULATION / 2.0
                d[2, 3] = avg + DELTA_MODULATION / 2.0
            y_arr[by * 8 : (by + 1) * 8, bx * 8 : (bx + 1) * 8] = idct2(d)

    y_mod = Image.fromarray(np.clip(y_arr, 0, 255).astype(np.uint8), mode="L")
    result_img = Image.merge("YCbCr", (y_mod, cb, cr)).convert("RGB")
    result_img.save(output_path, "PNG")


def decode(passphrase: str, carrier_path: str) -> str:
    with Image.open(carrier_path) as im:
        rgb_img = im.convert("RGB")
        y, _, _ = rgb_img.convert("YCbCr").split()

    y_arr = np.array(y, dtype=np.float32)
    h, w = y_arr.shape
    bh, bw = h // 8, w // 8
    total_blocks = bh * bw

    if total_blocks < HEADER_BLOCKS:
        raise ValueError("Image too small to contain a robust stego header")

    seed = prng.derive_seed(passphrase + "_robust")
    order = prng.build_permutation(seed, total_blocks)

    hdr_bits = []
    for i in range(16):
        votes = []
        for r in range(HEADER_REP):
            bidx = order[i * HEADER_REP + r]
            by, bx = bidx // bw, bidx % bw
            block = y_arr[by * 8 : (by + 1) * 8, bx * 8 : (bx + 1) * 8]
            d = dct2(block)
            votes.append(1 if d[3, 2] > d[2, 3] else 0)
        hdr_bits.append(1 if sum(votes) >= (HEADER_REP / 2.0) else 0)

    hdr_bytes = bits_to_bytes(hdr_bits)
    ecc_len = int.from_bytes(hdr_bytes[:2], "big")
    if ecc_len <= 0 or ecc_len > 20000:
        raise ValueError("Invalid robust header (wrong passphrase or image is not a robust carrier)")

    payload_bits_count = ecc_len * 8
    avail_payload_blocks = total_blocks - HEADER_BLOCKS
    if avail_payload_blocks < payload_bits_count:
        raise ValueError("Corrupted header size (payload exceeds image capacity)")

    rep = max(1, avail_payload_blocks // payload_bits_count)
    if rep % 2 == 0:
        rep -= 1
    rep = min(rep, 7)

    payload_start_slot = HEADER_BLOCKS
    extracted_payload_bits = []
    for i in range(payload_bits_count):
        votes = []
        for r in range(rep):
            slot = payload_start_slot + i * rep + r
            if slot >= total_blocks:
                break
            bidx = order[slot]
            by, bx = bidx // bw, bidx % bw
            block = y_arr[by * 8 : (by + 1) * 8, bx * 8 : (bx + 1) * 8]
            d = dct2(block)
            votes.append(1 if d[3, 2] > d[2, 3] else 0)
        extracted_payload_bits.append(1 if sum(votes) > (len(votes) / 2.0) else 0)

    ecc_packet = bits_to_bytes(extracted_payload_bits)[:ecc_len]
    rs = reedsolo.RSCodec(RS_PARITY_BYTES)
    try:
        decoded_packet = bytes(rs.decode(ecc_packet)[0])
    except Exception as exc:
        raise ValueError("Reed-Solomon error correction failed (image is severely degraded or wrong passphrase)") from exc

    if not decoded_packet.startswith(MAGIC_ROBUST):
        raise ValueError("Robust magic mismatch (wrong passphrase or image is not a robust carrier)")

    sealed_len = int.from_bytes(decoded_packet[4:8], "big")
    sealed = decoded_packet[8 : 8 + sealed_len]
    pt = crypto.open_sealed(passphrase, bytes(sealed))
    return pt.decode("utf-8")
