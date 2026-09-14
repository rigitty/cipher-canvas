import io
import pytest
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient

from cipher_engine.api.server import app

TEST_PASSPHRASE = "correct horse battery staple"


@pytest.fixture
def passphrase() -> str:
    return TEST_PASSPHRASE


@pytest.fixture
def sample_carrier_rgb() -> Image.Image:
    """Creates a 100x100 synthetic RGB test image with smooth gradient and texture."""
    img = Image.new("RGB", (100, 100), color=(0, 128, 255))
    for y in range(100):
        for x in range(100):
            img.putpixel((x, y), (x % 256, y % 256, (x * y) % 256))
    return img


@pytest.fixture
def sample_carrier_rgba() -> Image.Image:
    """Creates a 100x100 RGBA image with semi-transparent and opaque pixels."""
    img = Image.new("RGBA", (100, 100), color=(100, 150, 200, 255))
    for y in range(100):
        for x in range(100):
            alpha = 0 if (x < 10 and y < 10) else 255
            img.putpixel((x, y), (x % 256, y % 256, (x * 2) % 256, alpha))
    return img


@pytest.fixture
def large_carrier() -> Image.Image:
    """Creates a 400x400 RGB carrier for large payloads or robust DCT testing."""
    img = Image.new("RGB", (400, 400), color=(80, 140, 200))
    for y in range(400):
        for x in range(400):
            img.putpixel((x, y), ((x + y) % 256, (x * 2) % 256, (y * 3) % 256))
    return img


@pytest.fixture
def api_client() -> TestClient:
    return TestClient(app)
