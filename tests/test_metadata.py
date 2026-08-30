from __future__ import annotations

from pathlib import Path

from img_dedupe.metadata import ImageMetadata, discover_images, read_metadata, sha256_of_file
from tests.imgen import pattern_image, save


def test_read_metadata_basic_fields(tmp_path: Path) -> None:
    img = pattern_image(seed=1, size=(64, 48))
    path = save(img, tmp_path / "a.png")
    meta = read_metadata(path)
    assert meta.width == 64
    assert meta.height == 48
    assert meta.file_size == path.stat().st_size
    assert meta.sha256 == sha256_of_file(path)


def test_sha256_of_file_is_deterministic(tmp_path: Path) -> None:
    img = pattern_image(seed=2)
    path = save(img, tmp_path / "b.png")
    assert sha256_of_file(path) == sha256_of_file(path)


def test_sha256_differs_for_different_content(tmp_path: Path) -> None:
    img_a = pattern_image(seed=3)
    img_b = pattern_image(seed=4)
    path_a = save(img_a, tmp_path / "a.png")
    path_b = save(img_b, tmp_path / "b.png")
    assert sha256_of_file(path_a) != sha256_of_file(path_b)


def test_pixel_count_and_aspect_ratio() -> None:
    meta = ImageMetadata(
        path=Path("x.png"),
        file_size=100,
        width=100,
        height=50,
        mode="RGB",
        format="PNG",
        mtime=0.0,
        sha256="abc",
    )
    assert meta.pixel_count == 5000
    assert meta.aspect_ratio == 2.0


def test_aspect_ratio_zero_height_does_not_raise() -> None:
    meta = ImageMetadata(
        path=Path("x.png"), file_size=1, width=10, height=0, mode="RGB", format="PNG", mtime=0.0, sha256="a"
    )
    assert meta.aspect_ratio == 0.0


def test_bytes_per_pixel() -> None:
    meta = ImageMetadata(
        path=Path("x.png"),
        file_size=1000,
        width=10,
        height=10,
        mode="RGB",
        format="PNG",
        mtime=0.0,
        sha256="a",
    )
    assert meta.bytes_per_pixel == 10.0


def test_discover_images_filters_by_extension(tmp_path: Path) -> None:
    save(pattern_image(seed=1), tmp_path / "a.png")
    save(pattern_image(seed=2), tmp_path / "b.jpg", fmt="JPEG")
    (tmp_path / "notes.txt").write_text("hello")

    found = discover_images(tmp_path, extensions=(".png",))
    assert [p.name for p in found] == ["a.png"]


def test_discover_images_recursive(tmp_path: Path) -> None:
    save(pattern_image(seed=1), tmp_path / "top.png")
    save(pattern_image(seed=2), tmp_path / "sub" / "nested.png")

    found_recursive = discover_images(tmp_path, recursive=True, extensions=(".png",))
    found_flat = discover_images(tmp_path, recursive=False, extensions=(".png",))

    assert {p.name for p in found_recursive} == {"top.png", "nested.png"}
    assert {p.name for p in found_flat} == {"top.png"}


def test_discover_images_min_size_filter(tmp_path: Path) -> None:
    small_path = save(pattern_image(size=(4, 4), seed=1), tmp_path / "small.png")
    big_path = save(pattern_image(size=(200, 200), seed=1), tmp_path / "big.png")

    small_size = small_path.stat().st_size
    big_size = big_path.stat().st_size
    assert small_size < big_size

    found = discover_images(tmp_path, extensions=(".png",), min_size=small_size + 1)
    assert [p.name for p in found] == ["big.png"]
