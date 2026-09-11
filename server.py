import argparse
import io
import mimetypes
from urllib.parse import quote

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from PIL import Image

import capacity
import crypto
import detection
import stego

app = FastAPI(title="Cipher Canvas Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Capacity-Bytes", "X-Bits-Written", "X-Filename", "X-Bit-Depth"],
)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def _load_image(data: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception:
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
    bit_depth: int = Form(1),
) -> Response:
    data = await carrier.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="carrier exceeds 50 MB limit")

    image = _load_image(data)
    bit_depth = max(1, min(4, int(bit_depth)))

    if message_file is not None:
        file_data = await message_file.read()
        filename = message_file.filename or "file.bin"
    else:
        file_data = message.encode("utf-8")
        filename = "message.txt"

    payload = stego.pack_payload(filename, file_data)
    try:
        output_image, bits = stego._embed_bytes(
            passphrase, payload, image, bit_depth=bit_depth
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    buffer = io.BytesIO()
    output_image.save(buffer, "PNG")

    width, height = image.size
    filename_bytes = len(filename.encode("utf-8"))
    limit = capacity.max_plaintext_bytes(
        width, height, filename_length=filename_bytes, bit_depth=bit_depth
    )

    return Response(
        content=buffer.getvalue(),
        media_type="image/png",
        headers={
            "X-Capacity-Bytes": str(limit),
            "X-Bits-Written": str(bits),
            "X-Filename": quote(filename),
            "X-Bit-Depth": str(bit_depth),
        },
    )


@app.post("/api/decode")
def decode(
    carrier: UploadFile = File(...),
    passphrase: str = Form(...),
) -> Response:
    image = _load_image(carrier.file.read())
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


@app.post("/api/inspect")
async def inspect(image: UploadFile = File(...)) -> JSONResponse:
    data = await image.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="image exceeds 50 MB limit")

    loaded_image = _load_image(data)
    try:
        analysis = detection.analyze_image(loaded_image)
        return JSONResponse(content=analysis)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"steganalysis failed: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cipher Canvas engine server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
