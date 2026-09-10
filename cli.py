import argparse
import sys

import capacity
import stego


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cipher-canvas",
        description="Secure steganography: AES-256-GCM + LSB + PRNG distribution",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    encode_parser = subparsers.add_parser("encode", help="hide a message in an image")
    encode_parser.add_argument("carrier", help="carrier image path")
    encode_parser.add_argument("output", help="output image path")
    encode_parser.add_argument("--passphrase", required=True, help="secret passphrase")
    message_group = encode_parser.add_mutually_exclusive_group(required=True)
    message_group.add_argument("--message", help="message text")
    message_group.add_argument("--message-file", help="file containing the message")

    decode_parser = subparsers.add_parser("decode", help="extract a hidden message")
    decode_parser.add_argument("carrier", help="carrier image path")
    decode_parser.add_argument("--passphrase", required=True, help="secret passphrase")

    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    args = build_parser().parse_args(argv)

    if args.command == "encode":
        if args.message_file:
            with open(args.message_file, "r", encoding="utf-8-sig") as file:
                message = file.read()
        else:
            message = args.message

        from PIL import Image

        width, height = Image.open(args.carrier).size
        limit = capacity.max_plaintext_bytes(width, height)
        print(f"carrier: {width}x{height}, capacity: {limit} plaintext bytes")
        if len(message.encode("utf-8")) > limit:
            print(f"error: message is {len(message)} bytes, exceeds capacity {limit}")
            return 1

        bits = stego.encode(args.passphrase, message, args.carrier, args.output)
        print(f"done: {bits} bits written to {args.output}")
        return 0

    if args.command == "decode":
        try:
            message = stego.decode(args.passphrase, args.carrier)
        except Exception as exc:
            print(f"error: {exc}")
            return 1
        print(message)
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
