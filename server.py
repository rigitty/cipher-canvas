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


import robust


@app.post("/api/encode")
def encode(
    carrier: UploadFile = File(...),
    passphrase: str = Form(...),
    message: str = Form(""),
    message_file: UploadFile | None = File(None),
    bit_depth: int = Form(1),
    mode: str = Form("stealth"),
) -> Response:
    data = carrier.file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="carrier exceeds 50 MB limit")

    image = _load_image(data)
    bit_depth = max(1, min(4, int(bit_depth)))

    if message_file is not None:
        file_data = message_file.file.read()
        filename = message_file.filename or "file.bin"
    else:
        file_data = message.encode("utf-8")
        filename = "message.txt"

    width, height = image.size

    if mode == "robust":
        # Robust DCT + Reed-Solomon Mode (JPEG/WhatsApp lossy resistant)
        try:
            text_to_hide = file_data.decode("utf-8", errors="replace")
            result_img = robust.encode_image(passphrase, text_to_hide, image)
            buffer = io.BytesIO()
            result_img.save(buffer, "PNG")
            out_bytes = buffer.getvalue()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        limit = capacity.max_robust_capacity_bytes(width, height)
        return Response(
            content=out_bytes,
            media_type="image/png",
            headers={
                "X-Capacity-Bytes": str(limit),
                "X-Bits-Written": str(len(file_data) * 8),
                "X-Filename": quote(filename),
                "X-Bit-Depth": "DCT",
                "X-Mode": "robust",
            },
        )

    # Standard Stealth LSB Mode
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
            "X-Mode": "stealth",
        },
    )


@app.post("/api/decode")
def decode(
    carrier: UploadFile = File(...),
    passphrase: str = Form(...),
) -> Response:
    data = carrier.file.read()
    image = _load_image(data)

    # 1. First try standard Stealth LSB decode
    try:
        payload = stego._extract_bytes(passphrase, image)
        filename, file_data = stego.unpack_payload(payload)
        media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return Response(
            content=file_data,
            media_type=media_type,
            headers={"X-Filename": quote(filename), "X-Mode": "stealth"},
        )
    except Exception:
        # 2. If LSB fails, automatically try Robust DCT + Reed-Solomon decode!
        try:
            recovered_text = robust.decode_image(passphrase, image)
            return Response(
                content=recovered_text.encode("utf-8"),
                media_type="text/plain; charset=utf-8",
                headers={"X-Filename": quote("recovered_message.txt"), "X-Mode": "robust"},
            )
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Payload not found or invalid passphrase (checked both LSB Stealth and Robust DCT modes)",
            )


@app.post("/api/inspect")
def inspect(image: UploadFile = File(...)) -> JSONResponse:
    data = image.file.read()
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
