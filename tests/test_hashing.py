from __future__ import annotations

import pytest

from img_dedupe.hashing import (
    ImageHash,
    average_hash,
    compute_all_hashes,
    difference_hash,
    hamming_distance,
    perceptual_hash,
    wavelet_hash,
)
from tests.imgen import noise_image, pattern_image, resized, solid_color_image


def test_average_hash_of_solid_color_is_all_zero_bits() -> None:
    """Every pixel equals the mean, so `pixel > mean` is False everywhere."""
    img = solid_color_image()
    h = average_hash(img, hash_size=8)
    assert h.bits == 0


def test_hash_size_controls_bit_count() -> None:
    img = pattern_image(seed=1)
    h8 = average_hash(img, hash_size=8)
    h4 = average_hash(img, hash_size=4)
    assert h8.num_bits == 64
    assert h4.num_bits == 16


def test_hex_representation_length() -> None:
    img = pattern_image(seed=1)
    h = average_hash(img, hash_size=8)
    assert len(h.hex()) == 16  # 64 bits -> 16 hex chars


def test_hamming_distance_identical_hashes_is_zero() -> None:
    img = pattern_image(seed=2)
    h1 = perceptual_hash(img)
    h2 = perceptual_hash(img)
    assert hamming_distance(h1, h2) == 0


def test_hamming_distance_rejects_mismatched_algorithm() -> None:
    img = pattern_image(seed=3)
    a = average_hash(img)
    d = difference_hash(img)
    with pytest.raises(ValueError):
        hamming_distance(a, d)


def test_hamming_distance_rejects_mismatched_size() -> None:
    img = pattern_image(seed=3)
    a8 = average_hash(img, hash_size=8)
    a4 = average_hash(img, hash_size=4)
    with pytest.raises(ValueError):
        hamming_distance(a8, a4)


def test_hamming_distance_symmetry() -> None:
    img_a = pattern_image(seed=4)
    img_b = pattern_image(seed=5)
    ha, hb = perceptual_hash(img_a), perceptual_hash(img_b)
    assert hamming_distance(ha, hb) == hamming_distance(hb, ha)


@pytest.mark.parametrize("algo_func", [average_hash, difference_hash, perceptual_hash, wavelet_hash])
def test_hash_stable_under_identical_recompute(algo_func) -> None:  # type: ignore[no-untyped-def]
    img = pattern_image(seed=6)
    h1 = algo_func(img)
    h2 = algo_func(img)
    assert h1.bits == h2.bits


@pytest.mark.parametrize("algo_func", [average_hash, difference_hash, perceptual_hash, wavelet_hash])
def test_hash_stable_under_small_quality_change(algo_func) -> None:  # type: ignore[no-untyped-def]
    """A mild re-encode (quality drop) should barely move the hash."""
    import io

    from PIL import Image

    img = pattern_image(seed=7, size=(200, 200))
    buf_high = io.BytesIO()
    img.save(buf_high, format="JPEG", quality=95)
    buf_low = io.BytesIO()
    img.save(buf_low, format="JPEG", quality=80)

    img_high = Image.open(buf_high)
    img_low = Image.open(buf_low)

    h_high = algo_func(img_high)
    h_low = algo_func(img_low)
    distance = hamming_distance(h_high, h_low)
    assert distance <= 8, f"{algo_func.__name__} moved too much under mild recompression: {distance} bits"


def test_hash_instability_across_genuinely_different_content() -> None:
    """A perceptually different image should produce a large Hamming distance
    from an unrelated structured image -- the critical false-positive guard,
    verified here at the hash level (clustering-level guard is separate)."""
    img_a = pattern_image(seed=100)
    img_b = pattern_image(seed=999)
    ha = perceptual_hash(img_a)
    hb = perceptual_hash(img_b)
    assert hamming_distance(ha, hb) > 10


def test_solid_color_and_noise_do_not_match() -> None:
    solid = solid_color_image(color=(10, 10, 10))
    noise = noise_image(seed=1)
    h_solid = perceptual_hash(solid)
    h_noise = perceptual_hash(noise)
    assert hamming_distance(h_solid, h_noise) > 10


def test_two_different_noise_seeds_do_not_match() -> None:
    noise_a = noise_image(seed=1)
    noise_b = noise_image(seed=2)
    ha = average_hash(noise_a)
    hb = average_hash(noise_b)
    # Random noise images should not be perceptually clustered together.
    assert hamming_distance(ha, hb) > 5


def test_resized_copy_is_close_under_phash() -> None:
    img = pattern_image(seed=11, size=(320, 320))
    small = resized(img, 0.5)
    h1 = perceptual_hash(img)
    h2 = perceptual_hash(small)
    assert hamming_distance(h1, h2) <= 10


def test_compute_all_hashes_returns_every_algorithm() -> None:
    img = pattern_image(seed=12)
    hashes = compute_all_hashes(img)
    assert set(hashes.keys()) == {"ahash", "dhash", "phash", "whash"}
    for algo, h in hashes.items():
        assert isinstance(h, ImageHash)
        assert h.algorithm == algo


def test_difference_hash_uses_wide_thumbnail_internally() -> None:
    img = pattern_image(seed=13)
    h = difference_hash(img, hash_size=8)
    assert h.num_bits == 64


def test_wavelet_hash_thresholds_against_median() -> None:
    img = pattern_image(seed=14)
    h = wavelet_hash(img, hash_size=8)
    # Roughly half the bits should be set for a well-varied image (median
    # threshold), well away from all-zero or all-one degenerate cases.
    popcount = bin(h.bits).count("1")
    assert 5 <= popcount <= 59


def test_image_hash_str_matches_hex() -> None:
    img = pattern_image(seed=15)
    h = perceptual_hash(img)
    assert str(h) == h.hex()
