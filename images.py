from PIL import Image


def print_bits(value: int) -> str:
    return format(value, "08b")


def create_sample_image(path: str = "samples/sample.png", size: int = 100) -> None:
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    image = Image.new("RGB", (size, size), color=(0, 128, 255))
    for y in range(size):
        for x in range(size):
            image.putpixel((x, y), (x % 256, y % 256, (x * y) % 256))
    image.save(path)
    print(f"sample image saved: {path} ({size}x{size})")


def main() -> None:
    create_sample_image()
    image = Image.open("samples/sample.png")

    x, y = 50, 50
    r, g, b = image.getpixel((x, y))
    print(f"pixel ({x}, {y}) -> R={r} G={g} B={b}")

    for name, channel in (("R", r), ("G", g), ("B", b)):
        print(f"{name} = {channel:>3} -> bits: {print_bits(channel)}")


if __name__ == "__main__":
    main()
