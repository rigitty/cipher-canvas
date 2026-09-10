import argparse
import io

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from PIL import Image

import capacity
import stego

app = FastAPI(title="Cipher Canvas Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
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
) -> Response:
    data = await carrier.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="carrier exceeds 50 MB limit")

    image = _load_image(data)

    if message_file is not None:
        message = (await message_file.read()).decode("utf-8-sig")

    message_bytes = message.encode("utf-8")
    width, height = image.size
    limit = capacity.max_plaintext_bytes(width, height)
    if len(message_bytes) > limit:
        raise HTTPException(
            status_code=400,
            detail=f"message is {len(message_bytes)} bytes, "
            f"carrier capacity is {limit} bytes",
        )

    try:
        output_image, bits = stego._embed(passphrase, message, image)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    buffer = io.BytesIO()
    output_image.save(buffer, format="PNG")
    return Response(
        content=buffer.getvalue(),
        media_type="image/png",
        headers={
            "X-Capacity-Bytes": str(limit),
            "X-Bits-Written": str(bits),
        },
    )


@app.post("/api/decode")
def decode(
    carrier: UploadFile = File(...),
    passphrase: str = Form(...),
) -> dict:
    data = carrier.file.read()
    image = _load_image(data)
    try:
        message = stego._extract(passphrase, image)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"message": message}


def main() -> None:
    parser = argparse.ArgumentParser(description="Cipher Canvas engine server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
