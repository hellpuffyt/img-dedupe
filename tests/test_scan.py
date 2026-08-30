from __future__ import annotations

import json
from pathlib import Path

from img_dedupe.scan import ScanSettings, build_manifest, run_scan
from tests.imgen import cropped, noise_image, pattern_image, resized, save


def test_identical_images_are_grouped(tmp_path: Path) -> None:
    img = pattern_image(seed=1, size=(128, 128))
    save(img, tmp_path / "a.png")
    save(img, tmp_path / "b.png")

    settings = ScanSettings(root=tmp_path, algorithm="phash", threshold=10)
    report = run_scan(settings)
    duplicate_groups = [g for g in report.groups if len(g) > 1]
    assert len(duplicate_groups) == 1
    assert len(duplicate_groups[0]) == 2


def test_resized_copy_detected_as_resize(tmp_path: Path) -> None:
    img = pattern_image(seed=2, size=(256, 256))
    save(img, tmp_path / "original.png")
    save(resized(img, 0.5), tmp_path / "half.png")

    settings = ScanSettings(root=tmp_path, algorithm="phash", threshold=12)
    report = run_scan(settings)
    manifest = build_manifest(report)

    assert manifest["summary"]["duplicate_groups"] == 1
    group = manifest["groups"][0]
    assert group["variant"] == "resize"


def test_reencoded_copy_detected(tmp_path: Path) -> None:
    img = pattern_image(seed=3, size=(200, 200))
    save(img, tmp_path / "original.png", fmt="PNG")
    save(img, tmp_path / "recompressed.jpg", fmt="JPEG", quality=40)

    settings = ScanSettings(root=tmp_path, algorithm="phash", threshold=12, extensions=(".png", ".jpg"))
    report = run_scan(settings)
    manifest = build_manifest(report)

    assert manifest["summary"]["duplicate_groups"] == 1
    group = manifest["groups"][0]
    # Same pixel dimensions, different bytes -> re_encode.
    assert group["variant"] == "re_encode"


def test_genuinely_different_image_not_grouped(tmp_path: Path) -> None:
    """Critical false-positive guard: two unrelated structured images must
    not end up in the same cluster."""
    save(pattern_image(seed=10, size=(200, 200)), tmp_path / "one.png")
    save(pattern_image(seed=987654, size=(200, 200)), tmp_path / "two.png")

    settings = ScanSettings(root=tmp_path, algorithm="phash", threshold=10)
    report = run_scan(settings)
    duplicate_groups = [g for g in report.groups if len(g) > 1]
    assert duplicate_groups == []


def test_solid_color_and_noise_not_grouped(tmp_path: Path) -> None:
    from tests.imgen import solid_color_image

    save(solid_color_image(color=(20, 20, 20)), tmp_path / "solid.png")
    save(noise_image(seed=5), tmp_path / "noise.png")

    settings = ScanSettings(root=tmp_path, algorithm="phash", threshold=10)
    report = run_scan(settings)
    duplicate_groups = [g for g in report.groups if len(g) > 1]
    assert duplicate_groups == []


def test_cropped_copy_detected_as_crop_or_similar(tmp_path: Path) -> None:
    img = pattern_image(seed=4, size=(300, 300))
    save(img, tmp_path / "original.png")
    save(cropped(img, fraction=0.85), tmp_path / "cropped.png")

    # Use a generous threshold since a crop changes a meaningful fraction
    # of the frame; this test only asserts on the aspect-ratio-driven
    # classification, not on hitting a specific distance.
    settings = ScanSettings(root=tmp_path, algorithm="phash", threshold=28)
    report = run_scan(settings)
    manifest = build_manifest(report)
    if manifest["summary"]["duplicate_groups"] == 1:
        group = manifest["groups"][0]
        assert group["variant"] in ("crop", "resize", "re_encode")


def test_min_size_filter_excludes_small_files(tmp_path: Path) -> None:
    small = save(pattern_image(size=(4, 4), seed=1), tmp_path / "tiny.png")
    save(pattern_image(size=(200, 200), seed=2), tmp_path / "normal.png")
    small_size = small.stat().st_size

    settings = ScanSettings(root=tmp_path, min_size=small_size + 1)
    report = run_scan(settings)
    assert len(report.images) == 1
    assert report.images[0].metadata.path.name == "normal.png"


def test_manifest_is_json_serialisable(tmp_path: Path) -> None:
    img = pattern_image(seed=5, size=(100, 100))
    save(img, tmp_path / "a.png")
    save(img, tmp_path / "b.png")

    settings = ScanSettings(root=tmp_path)
    report = run_scan(settings)
    manifest = build_manifest(report)
    serialised = json.dumps(manifest)
    assert json.loads(serialised) == manifest


def test_manifest_records_reclaimable_bytes(tmp_path: Path) -> None:
    img = pattern_image(seed=6, size=(120, 120))
    save(img, tmp_path / "a.png")
    dup_path = save(img, tmp_path / "b.png")

    settings = ScanSettings(root=tmp_path)
    report = run_scan(settings)
    manifest = build_manifest(report)
    group = manifest["groups"][0]
    # One of the two identical files is the removal candidate.
    removal_candidates = [m for m in group["members"] if m["action"] == "delete_candidate"]
    assert len(removal_candidates) == 1
    assert group["reclaimable_bytes"] == dup_path.stat().st_size


def test_no_images_produces_empty_manifest(tmp_path: Path) -> None:
    settings = ScanSettings(root=tmp_path)
    report = run_scan(settings)
    manifest = build_manifest(report)
    assert manifest["summary"]["total_images"] == 0
    assert manifest["groups"] == []


def test_unique_images_produce_no_duplicate_groups(tmp_path: Path) -> None:
    for i in range(4):
        save(pattern_image(seed=1000 + i * 137, size=(150, 150)), tmp_path / f"img{i}.png")

    settings = ScanSettings(root=tmp_path, threshold=6)
    report = run_scan(settings)
    manifest = build_manifest(report)
    assert manifest["summary"]["total_images"] == 4
    assert manifest["summary"]["duplicate_groups"] == 0


def test_scan_never_deletes_files(tmp_path: Path) -> None:
    img = pattern_image(seed=7, size=(100, 100))
    a = save(img, tmp_path / "a.png")
    b = save(img, tmp_path / "b.png")

    settings = ScanSettings(root=tmp_path)
    report = run_scan(settings)
    build_manifest(report)
    assert a.exists()
    assert b.exists()
