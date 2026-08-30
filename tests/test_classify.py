from __future__ import annotations

from pathlib import Path

from img_dedupe.classify import classify_pair, dominant_variant
from img_dedupe.metadata import ImageMetadata


def _meta(**overrides: object) -> ImageMetadata:
    defaults: dict[str, object] = dict(
        path=Path("x.png"),
        file_size=1000,
        width=100,
        height=100,
        mode="RGB",
        format="PNG",
        mtime=0.0,
        sha256="hash-a",
    )
    defaults.update(overrides)
    return ImageMetadata(**defaults)  # type: ignore[arg-type]


def test_identical_sha256_is_exact_duplicate() -> None:
    a = _meta(sha256="same")
    b = _meta(sha256="same", path=Path("y.png"))
    assert classify_pair(a, b, hash_distance=0) == "exact_duplicate"


def test_same_dimensions_different_bytes_is_reencode() -> None:
    a = _meta(sha256="a", width=200, height=100)
    b = _meta(sha256="b", width=200, height=100)
    assert classify_pair(a, b, hash_distance=3) == "re_encode"


def test_same_aspect_ratio_different_dimensions_is_resize() -> None:
    a = _meta(sha256="a", width=200, height=100)
    b = _meta(sha256="b", width=100, height=50)
    assert classify_pair(a, b, hash_distance=4) == "resize"


def test_different_aspect_ratio_is_crop() -> None:
    a = _meta(sha256="a", width=200, height=100)  # ratio 2.0
    b = _meta(sha256="b", width=100, height=100)  # ratio 1.0
    assert classify_pair(a, b, hash_distance=8) == "crop"


def test_zero_dimension_falls_back_to_similar() -> None:
    a = _meta(sha256="a", width=0, height=100)
    b = _meta(sha256="b", width=100, height=100)
    assert classify_pair(a, b, hash_distance=8) == "similar"


def test_aspect_ratio_tolerance_absorbs_rounding_noise() -> None:
    # 300x200 vs 299x199: aspect ratios very close but dims differ -> resize
    a = _meta(sha256="a", width=300, height=200)
    b = _meta(sha256="b", width=299, height=199)
    assert classify_pair(a, b, hash_distance=2) == "resize"


def test_dominant_variant_prioritises_exact_duplicate() -> None:
    assert dominant_variant(["crop", "exact_duplicate", "resize"]) == "exact_duplicate"


def test_dominant_variant_falls_through_priority_order() -> None:
    assert dominant_variant(["crop", "resize"]) == "resize"
    assert dominant_variant(["crop"]) == "crop"
    assert dominant_variant(["similar"]) == "similar"


def test_dominant_variant_empty_list_defaults_to_similar() -> None:
    assert dominant_variant([]) == "similar"
