def embed_bit(byte: int, bit: int) -> int:
    return (byte & 0xFE) | (bit & 0x01)


def extract_bit(byte: int) -> int:
    return byte & 0x01


def embed_bits(byte: int, value: int, bits: int = 1) -> int:
    mask = (0xFF << bits) & 0xFF
    val_mask = (1 << bits) - 1
    return (byte & mask) | (value & val_mask)


def extract_bits(byte: int, bits: int = 1) -> int:
    val_mask = (1 << bits) - 1
    return byte & val_mask


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
