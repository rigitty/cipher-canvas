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
import robust
import sharding
import stego
import zipfile

app = FastAPI(title="Cipher Canvas Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Capacity-Bytes",
        "X-Bits-Written",
        "X-Filename",
        "X-Bit-Depth",
        "X-Shard-Count",
        "X-Group-ID",
    ],
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


@app.post("/api/encode/shard")
def encode_shard(
    carriers: list[UploadFile] = File(...),
    passphrase: str = Form(...),
    message: str = Form(""),
    message_file: UploadFile | None = File(None),
    bit_depth: int = Form(1),
) -> Response:
    if len(carriers) < 2:
        raise HTTPException(
            status_code=400, detail="Multi-image sharding requires at least 2 carrier images."
        )

    images = []
    for c in carriers:
        c_bytes = c.file.read()
        if len(c_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=400, detail=f"Image {c.filename} exceeds 50MB limit.")
        images.append(_load_image(c_bytes))

    bit_depth = max(1, min(4, int(bit_depth)))

    if message_file is not None:
        file_data = message_file.file.read()
        filename = message_file.filename or "file.bin"
    else:
        file_data = message.encode("utf-8")
        filename = "message.txt"

    try:
        stego_images = sharding.shard_payload(
            passphrase=passphrase,
            filename=filename,
            payload_data=file_data,
            carrier_images=images,
            bit_depth=bit_depth,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sharding failed: {exc}")

    # Package all stego images into a ZIP archive
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx, s_img in enumerate(stego_images):
            img_buf = io.BytesIO()
            s_img.save(img_buf, "PNG")
            zf.writestr(f"shard_{idx+1}_of_{len(stego_images)}.png", img_buf.getvalue())

    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "X-Filename": quote(f"sharded_{filename}.zip"),
            "X-Shard-Count": str(len(stego_images)),
            "X-Bit-Depth": str(bit_depth),
        },
    )


@app.post("/api/decode/shard")
def decode_shard(
    shards: list[UploadFile] = File(...),
    passphrase: str = Form(...),
) -> Response:
    if not shards:
        raise HTTPException(status_code=400, detail="No shard images uploaded.")

    images = []
    for s in shards:
        s_bytes = s.file.read()
        images.append(_load_image(s_bytes))

    try:
        filename, file_data, report = sharding.assemble_shards(passphrase, images)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sharding reassembly failed: {exc}")

    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return Response(
        content=file_data,
        media_type=media_type,
        headers={
            "X-Filename": quote(filename),
            "X-Group-ID": report["group_id"],
            "X-Shard-Count": str(report["total_shards"]),
        },
    )


@app.post("/api/decode")
def decode(
    carrier: UploadFile = File(...),
    passphrase: str = Form(...),
) -> Response:
    data = carrier.file.read()
    image = _load_image(data)

    # 1. First check if this is an individual shard from a multi-image set
    shard_meta = sharding.inspect_shard(passphrase, image)
    if shard_meta is not None:
        # It's a shard, inform user that other parts are required
        raise HTTPException(
            status_code=422,
            detail=(
                f"This image is Shard #{shard_meta['shard_index'] + 1} of a {shard_meta['total_shards']}-part Sharded Carrier "
                f"(Group ID: {shard_meta['group_id'][:8]}...). "
                f"Please switch to Multi-Image Shard Decode tab to assemble all {shard_meta['total_shards']} parts."
            ),
        )

    # 2. Standard Stealth LSB decode
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
        # 3. If LSB fails, automatically try Robust DCT + Reed-Solomon decode!
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
                detail="Payload not found or invalid passphrase (checked LSB Stealth, Robust DCT, and Shards)",
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


def _watch_parent_process(parent_pid: int | None = None) -> None:
    """Background watchdog thread that ensures server exits when parent GUI process closes."""
    import ctypes
    import os
    import threading
    import time

    pid = parent_pid or os.getppid()
    if pid <= 1:
        return

    def _checker():
        kernel32 = getattr(ctypes, "windll", None) and getattr(ctypes.windll, "kernel32", None)
        if not kernel32:
            return
        SYNCHRONIZE = 0x00100000
        while True:
            time.sleep(1.5)
            try:
                handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
                if not handle:
                    os._exit(0)
                res = kernel32.WaitForSingleObject(handle, 0)
                kernel32.CloseHandle(handle)
                if res != 0x00000102:  # WAIT_TIMEOUT (0x102) means process is still alive
                    os._exit(0)
            except Exception:
                break

    thread = threading.Thread(target=_checker, daemon=True, name="ParentWatchdog")
    thread.start()


def main() -> None:
    parser = argparse.ArgumentParser(description="Cipher Canvas engine server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument("--parent-pid", default=None, type=int)
    args = parser.parse_args()

    _watch_parent_process(args.parent_pid)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
