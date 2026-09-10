def embed_bit(byte: int, bit: int) -> int:
    return (byte & 0xFE) | (bit & 0x01)


def extract_bit(byte: int) -> int:
    return byte & 0x01


def embed_byte(pixel_channels: list[int], data_byte: int) -> list[int]:
    for i in range(8):
        bit = (data_byte >> i) & 0x01
        pixel_channels[i] = embed_bit(pixel_channels[i], bit)
    return pixel_channels


def extract_byte(pixel_channels: list[int]) -> int:
    data_byte = 0
    for i in range(8):
        bit = extract_bit(pixel_channels[i])
        data_byte |= bit << i
    return data_byte


def demo() -> None:
    secret = ord("A")
    print(f"secret: '{chr(secret)}' = 0x{secret:02X} = {format(secret, '08b')}")

    carriers = [10, 20, 30, 40, 50, 60, 70, 80]
    print(f"carriers before: {carriers}")

    modified = embed_byte(carriers[:], secret)
    print(f"carriers after : {modified}")

    recovered = extract_byte(modified)
    print(f"recovered: '{chr(recovered)}' = 0x{recovered:02X} = {format(recovered, '08b')}")
    print(f"round-trip ok: {recovered == secret}")

    diff = sum(1 for a, b in zip(carriers, modified) if a != b)
    print(f"changed {diff}/8 carrier bytes (max +/-1 each)")


if __name__ == "__main__":
    demo()
