import pytest
from PIL import Image

from cipher_engine.core import sharding


def test_sharding_homogeneous_carriers(sample_carrier_rgb: Image.Image, passphrase: str):
    c1 = sample_carrier_rgb.copy()
    c2 = sample_carrier_rgb.copy()
    c3 = sample_carrier_rgb.copy()

    payload = b"Multi-image sharded secret payload across 3 equal carriers."
    shards = sharding.shard_payload(
        passphrase=passphrase,
        filename="notes.txt",
        payload_data=payload,
        carrier_images=[c1, c2, c3],
        bit_depth=1,
    )
    assert len(shards) == 3

    # Shuffle shards and reassemble
    shuffled = [shards[2], shards[0], shards[1]]
    filename, data, report = sharding.assemble_shards(passphrase, shuffled)

    assert filename == "notes.txt"
    assert data == payload
    assert report["total_shards"] == 3


def test_sharding_heterogeneous_carriers(passphrase: str):
    """Verifies that proportional chunk allocation fits carriers with drastically different resolutions."""
    c_small = Image.new("RGB", (100, 100), (255, 0, 0))    # ~3.6 KB capacity
    c_large = Image.new("RGB", (1000, 800), (0, 255, 0))   # ~290 KB capacity
    c_medium = Image.new("RGB", (300, 300), (0, 0, 255))   # ~33 KB capacity

    payload = b"Heterogeneous resolution test: small, large and medium carriers. " * 500  # ~33 KB
    shards = sharding.shard_payload(
        passphrase=passphrase,
        filename="big_doc.pdf",
        payload_data=payload,
        carrier_images=[c_small, c_large, c_medium],
        bit_depth=1,
    )
    assert len(shards) == 3

    filename, data, report = sharding.assemble_shards(passphrase, shards)
    assert filename == "big_doc.pdf"
    assert data == payload


def test_missing_shard_rejected(sample_carrier_rgb: Image.Image, passphrase: str):
    c1 = sample_carrier_rgb.copy()
    c2 = sample_carrier_rgb.copy()
    c3 = sample_carrier_rgb.copy()

    shards = sharding.shard_payload(
        passphrase=passphrase,
        filename="doc.txt",
        payload_data=b"Three shard payload",
        carrier_images=[c1, c2, c3],
    )

    # Supply only 2 of 3 shards
    with pytest.raises(ValueError, match="Missing shards"):
        sharding.assemble_shards(passphrase, shards[:2])


def test_inspect_shard(sample_carrier_rgb: Image.Image, passphrase: str):
    c1 = sample_carrier_rgb.copy()
    c2 = sample_carrier_rgb.copy()

    shards = sharding.shard_payload(
        passphrase=passphrase,
        filename="info.txt",
        payload_data=b"Inspectable shard",
        carrier_images=[c1, c2],
    )

    info = sharding.inspect_shard(passphrase, shards[0])
    assert info is not None
    assert info["shard_index"] == 0
    assert info["total_shards"] == 2
    assert "group_id" in info
