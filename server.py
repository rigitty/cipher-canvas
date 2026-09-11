import argparse
import io
import mimetypes
from urllib.parse import quote

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from PIL import Image

import capacity
import crypto
import stego

app = FastAPI(title="Cipher Canvas Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Capacity-Bytes", "X-Bits-Written", "X-Filename", "X-Mode"],
)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def _load_image(data: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="file is not a valid image")
    return image


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "engine": "aes-256-gcm + lsb + prng",
        "version": "1.0.0",
    }


@app.post("/api/encode")
async def encode(
    carrier: UploadFile = File(...),
    passphrase: str = Form(...),
    message: str = Form(""),
    message_file: UploadFile | None = File(None),
    mode: str = Form("normal"),
) -> Response:
    data = await carrier.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="carrier exceeds 50 MB limit")

    image = _load_image(data)

    if message_file is not None:
        file_data = await message_file.read()
        filename = message_file.filename or "file.bin"
    else:
        file_data = message.encode("utf-8")
        filename = "message.txt"

    payload = stego.pack_payload(filename, file_data)
    try:
        if mode == "robust":
            import robust

            output_image, bits, meta = robust.encode_robust(passphrase, payload, image)
            fmt = "JPEG"
            media_type = "image/jpeg"
        else:
            output_image, bits = stego._embed_bytes(passphrase, payload, image)
            fmt = "PNG"
            media_type = "image/png"
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    buffer = io.BytesIO()
    if fmt == "JPEG":
        output_image.save(buffer, "JPEG", quality=75, optimize=True)
    else:
        output_image.save(buffer, "PNG")

    width, height = image.size
    filename_bytes = len(filename.encode("utf-8"))
    if mode == "robust":
        import robust

        total_bytes = width * height * 3 // 8
        available = total_bytes - robust.INDEX_REPEAT * robust.INDEX_BYTES
        limit = max(
            0,
            available // robust.MAX_COPIES
            - stego.HEADER_SIZE
            - crypto.SALT_SIZE
            - crypto.NONCE_SIZE
            - crypto.TAG_SIZE
            - filename_bytes
            - 1,
        )
    else:
        limit = capacity.max_plaintext_bytes(
            width, height, filename_length=filename_bytes
        )

    return Response(
        content=buffer.getvalue(),
        media_type=media_type,
        headers={
            "X-Capacity-Bytes": str(limit),
            "X-Bits-Written": str(bits),
            "X-Filename": quote(filename),
            "X-Mode": mode,
        },
    )


@app.post("/api/decode")
def decode(
    carrier: UploadFile = File(...),
    passphrase: str = Form(...),
) -> Response:
    image = _load_image(carrier.file.read())
    payload = None
    try:
        import robust

        payload = robust.decode_robust(passphrase, image)
    except Exception:
        pass
    if payload is None:
        try:
            payload = stego._extract_bytes(passphrase, image)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    filename, file_data = stego.unpack_payload(payload)
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return Response(
        content=file_data,
        media_type=media_type,
        headers={"X-Filename": quote(filename)},
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Cipher Canvas engine server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
