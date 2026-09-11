from PIL import Image

import crypto
import lsb
import prng

MAGIC = b"CSGA"
MAGIC_LEN = 4
LENGTH_SIZE = 4
HEADER_SIZE = MAGIC_LEN + LENGTH_SIZE


def bytes_to_bits(data: bytes) -> list[int]:
    bits: list[int] = []
    for byte in data:
        for i in range(8):
            bits.append((byte >> i) & 0x01)
    return bits


def bits_to_bytes(bits: list[int]) -> bytes:
    out = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(8):
            byte |= bits[i + j] << j
        out.append(byte)
    return bytes(out)


def pack_payload(filename: str, data: bytes) -> bytes:
    return filename.encode("utf-8") + b"\x00" + data


def unpack_payload(payload: bytes) -> tuple[str, bytes]:
    parts = payload.split(b"\x00", 1)
    if len(parts) == 1:
        return "message.txt", payload
    filename = parts[0].decode("utf-8", errors="replace").strip() or "file.bin"
    return filename, parts[1]


def _embed_bits(passphrase: str, bits: list[int], image: Image.Image) -> tuple[Image.Image, int]:
    image = image.convert("RGB")
    pixels = list(image.get_flattened_data())
    slot_count = len(pixels) * 3

    if len(bits) > slot_count:
        raise ValueError(
            f"payload too large: {len(bits)} bits > {slot_count} available slots"
        )

    order = prng.build_permutation(prng.derive_seed(passphrase), slot_count)

    for i, bit in enumerate(bits):
        slot = order[i]
        pixel_index = slot // 3
        channel = slot % 3
        r, g, b = pixels[pixel_index]
        new_value = lsb.embed_bit((r, g, b)[channel], bit)
        if channel == 0:
            pixels[pixel_index] = (new_value, g, b)
        elif channel == 1:
            pixels[pixel_index] = (r, new_value, b)
        else:
            pixels[pixel_index] = (r, g, new_value)

    image.putdata(pixels)
    return image, len(bits)


def _embed_bytes(passphrase: str, payload: bytes, image: Image.Image) -> tuple[Image.Image, int]:
    sealed = crypto.seal(passphrase, payload)
    full = MAGIC + len(sealed).to_bytes(LENGTH_SIZE, "big") + sealed
    return _embed_bits(passphrase, bytes_to_bits(full), image)


def _embed(passphrase: str, message: str, image: Image.Image) -> tuple[Image.Image, int]:
    return _embed_bytes(
        passphrase, pack_payload("message.txt", message.encode("utf-8")), image
    )


def encode(passphrase: str, message: str, carrier_path: str, output_path: str) -> int:
    if carrier_path.lower().endswith((".jpg", ".jpeg")):
        print(
            "warning: JPEG is lossy; its LSBs are already corrupted by compression, "
            "re-encoding will destroy embedded data"
        )

    image = Image.open(carrier_path)
    output_image, bits = _embed(passphrase, message, image)
    output_image.save(output_path)
    print(f"embedded {bits} bits ({bits // 8} bytes) into {image.width * image.height * 3} slots")
    return bits


def _read_bits(passphrase: str, image: Image.Image) -> list[int]:
    image = image.convert("RGB")
    pixels = list(image.get_flattened_data())
    slot_count = len(pixels) * 3

    order = prng.build_permutation(prng.derive_seed(passphrase), slot_count)
    bits = [0] * slot_count
    for i, slot in enumerate(order):
        pixel_index = slot // 3
        channel = slot % 3
        bits[i] = lsb.extract_bit(pixels[pixel_index][channel])
    return bits


def _extract_bytes(passphrase: str, image: Image.Image) -> bytes:
    bits = _read_bits(passphrase, image)

    header = bits_to_bytes(bits[: HEADER_SIZE * 8])
    if header[:MAGIC_LEN] != MAGIC:
        raise ValueError(
            "header magic not found (wrong passphrase or image is not a carrier)"
        )

    sealed_length = int.from_bytes(header[MAGIC_LEN:], "big")
    sealed = bits_to_bytes(
        bits[HEADER_SIZE * 8 : HEADER_SIZE * 8 + sealed_length * 8]
    )
    return crypto.open_sealed(passphrase, sealed)


def _extract(passphrase: str, image: Image.Image) -> str:
    _, data = unpack_payload(_extract_bytes(passphrase, image))
    return data.decode("utf-8")


def decode(passphrase: str, carrier_path: str) -> str:
    return _extract(passphrase, Image.open(carrier_path))


def demo() -> None:
    message = "top secret: meet at the pixel at midnight"
    passphrase = "correct horse battery staple"

    encode(passphrase, message, "sample.png", "carrier.png")
    recovered = decode(passphrase, "carrier.png")
    print(f"recovered message: {recovered}")
    print(f"round-trip ok     : {recovered == message}")

    carrier = Image.open("sample.png")
    output = Image.open("carrier.png")
    changed = sum(
        1
        for a, b in zip(
            carrier.get_flattened_data(), output.get_flattened_data()
        )
        if a != b
    )
    print(f"changed pixels    : {changed}/{carrier.width * carrier.height}")

    try:
        decode("wrong passphrase", "carrier.png")
        print("wrong pass        : ACCEPTED (bug!)")
    except Exception as exc:
        print(f"wrong pass        : rejected ({type(exc).__name__})")

    try:
        decode(passphrase, "sample.png")
        print("non-carrier       : ACCEPTED (bug!)")
    except Exception as exc:
        print(f"non-carrier       : rejected ({type(exc).__name__})")


if __name__ == "__main__":
    demo()
