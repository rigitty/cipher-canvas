import io
from fastapi.testclient import TestClient
from PIL import Image


def _image_to_bytes(image: Image.Image, format: str = "PNG") -> bytes:
    buf = io.BytesIO()
    image.save(buf, format=format)
    return buf.getvalue()


def test_api_health(api_client: TestClient):
    resp = api_client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "aes-256-gcm" in data["engine"]


def test_api_encode_and_decode_stealth(api_client: TestClient, sample_carrier_rgb: Image.Image):
    carrier_bytes = _image_to_bytes(sample_carrier_rgb)
    passphrase = "api-test-passphrase"
    secret_text = "Hello from FastAPI automated tests!"

    # 1. Encode
    encode_resp = api_client.post(
        "/api/encode",
        files={"carrier": ("carrier.png", carrier_bytes, "image/png")},
        data={
            "passphrase": passphrase,
            "message": secret_text,
            "bit_depth": "1",
            "mode": "stealth",
        },
    )
    assert encode_resp.status_code == 200
    assert encode_resp.headers["X-Mode"] == "stealth"
    assert "X-PSNR-dB" in encode_resp.headers
    assert "X-SSIM" in encode_resp.headers
    stego_png = encode_resp.content

    # 2. Decode
    decode_resp = api_client.post(
        "/api/decode",
        files={"carrier": ("stego.png", stego_png, "image/png")},
        data={"passphrase": passphrase},
    )
    assert decode_resp.status_code == 200
    assert decode_resp.text == secret_text


def test_api_inspect(api_client: TestClient, sample_carrier_rgb: Image.Image):
    carrier_bytes = _image_to_bytes(sample_carrier_rgb)
    resp = api_client.post(
        "/api/inspect",
        files={"image": ("test.png", carrier_bytes, "image/png")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "risk_score" in data
    assert "chi_square" in data
    assert "lsb_preview" in data


def test_api_metrics_compare(api_client: TestClient, sample_carrier_rgb: Image.Image):
    c_bytes = _image_to_bytes(sample_carrier_rgb)
    # create slightly modified image
    stego = sample_carrier_rgb.copy()
    stego.putpixel((0, 0), (255, 255, 255))
    s_bytes = _image_to_bytes(stego)

    resp = api_client.post(
        "/api/metrics/compare",
        files={
            "carrier": ("carrier.png", c_bytes, "image/png"),
            "stego": ("stego.png", s_bytes, "image/png"),
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "psnr_db" in data
    assert "ssim" in data
    assert "quality_tier" in data
