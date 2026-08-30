"""Perceptual image hashing, implemented from scratch on top of numpy + Pillow.

Four algorithms are provided:

* :func:`average_hash` (aHash) -- threshold each pixel of a small greyscale
  thumbnail against the mean pixel value.
* :func:`difference_hash` (dHash) -- threshold each pixel against its
  right-hand neighbour, capturing gradient direction rather than absolute
  brightness.
* :func:`perceptual_hash` (pHash) -- take the 2D Discrete Cosine Transform of
  a greyscale thumbnail (implemented by hand below, no scipy/opencv), keep
  the low-frequency corner, and threshold against the median. This is the
  most robust of the three to re-encoding, mild resizing and small colour
  shifts because it operates in the frequency domain rather than on raw
  pixel intensities.
* :func:`wavelet_hash` (wHash) -- a simplified Haar-wavelet hash: repeatedly
  average 2x2 blocks (one level of a Haar transform's low-pass band) down to
  a small thumbnail, then threshold against the median, similar in spirit to
  pHash but using a wavelet low-pass instead of a DCT.

Every hash is returned as a Python ``int`` (a bit field) alongside the side
length of the square hash grid, so two hashes can only be meaningfully
compared with :func:`hamming_distance` if they came from the same algorithm
and the same grid size.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from PIL import Image

HashAlgorithm = Literal["ahash", "dhash", "phash", "whash"]

ALL_ALGORITHMS: tuple[HashAlgorithm, ...] = ("ahash", "dhash", "phash", "whash")


@dataclass(frozen=True)
class ImageHash:
    """A perceptual hash: an integer bit field plus the grid size it came from."""

    algorithm: HashAlgorithm
    bits: int
    hash_size: int

    @property
    def num_bits(self) -> int:
        return self.hash_size * self.hash_size

    def hex(self) -> str:
        width = (self.num_bits + 3) // 4
        return format(self.bits, f"0{width}x")

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.hex()


def hamming_distance(a: ImageHash, b: ImageHash) -> int:
    """Count differing bits between two hashes of the same algorithm/size."""
    if a.algorithm != b.algorithm:
        raise ValueError(f"cannot compare {a.algorithm!r} hash with {b.algorithm!r} hash")
    if a.hash_size != b.hash_size:
        raise ValueError(f"cannot compare hashes of size {a.hash_size} and {b.hash_size}")
    return int(bin(a.bits ^ b.bits).count("1"))


def _to_grayscale_array(image: Image.Image, size: tuple[int, int]) -> np.ndarray:
    """Resize to ``size`` and convert to a float64 greyscale numpy array."""
    resized = image.convert("L").resize(size, Image.Resampling.LANCZOS)
    return np.asarray(resized, dtype=np.float64)


def _bits_from_bool_grid(grid: np.ndarray) -> int:
    """Pack a boolean grid (row-major) into a single Python int, MSB first."""
    bits = 0
    for value in grid.flatten():
        bits = (bits << 1) | int(bool(value))
    return bits


def average_hash(image: Image.Image, hash_size: int = 8) -> ImageHash:
    """aHash: threshold a small thumbnail against its own mean brightness."""
    arr = _to_grayscale_array(image, (hash_size, hash_size))
    mean = arr.mean()
    bits = _bits_from_bool_grid(arr > mean)
    return ImageHash("ahash", bits, hash_size)


def difference_hash(image: Image.Image, hash_size: int = 8) -> ImageHash:
    """dHash: threshold each pixel against its right-hand neighbour.

    Uses a thumbnail one column wider than the target hash grid so every
    output column has a right neighbour to compare against.
    """
    arr = _to_grayscale_array(image, (hash_size + 1, hash_size))
    diff = arr[:, :-1] > arr[:, 1:]
    bits = _bits_from_bool_grid(diff)
    return ImageHash("dhash", bits, hash_size)


def _dct_matrix(n: int) -> np.ndarray:
    """Build the orthonormal NxN DCT-II basis matrix.

    ``C[k, x] = alpha(k) * cos(pi / N * (x + 0.5) * k)`` with
    ``alpha(0) = sqrt(1/N)`` and ``alpha(k) = sqrt(2/N)`` for ``k > 0``.

    Applying ``C @ v`` performs a 1D orthonormal DCT-II of vector ``v``.
    This is a direct O(N^2) matrix formulation of the transform -- no FFT
    trick, no scipy -- which keeps the implementation easy to verify by hand
    for small N.
    """
    x = np.arange(n, dtype=np.float64)
    k = np.arange(n, dtype=np.float64).reshape(-1, 1)
    basis = np.cos(np.pi / n * (x + 0.5) * k)
    alpha = np.full((n, 1), np.sqrt(2.0 / n))
    alpha[0, 0] = np.sqrt(1.0 / n)
    return alpha * basis


def dct2(matrix: np.ndarray) -> np.ndarray:
    """2D orthonormal DCT-II of a square matrix, via ``C @ M @ C.T``."""
    n = matrix.shape[0]
    if matrix.shape[0] != matrix.shape[1]:
        raise ValueError("dct2 requires a square input matrix")
    c = _dct_matrix(n)
    result: np.ndarray = c @ matrix @ c.T
    return result


def perceptual_hash(image: Image.Image, hash_size: int = 8, highfreq_factor: int = 4) -> ImageHash:
    """pHash: threshold the low-frequency corner of a DCT against its median.

    The thumbnail is deliberately larger (``hash_size * highfreq_factor``)
    than the final hash grid so the DCT has real frequency content to work
    with; only the top-left ``hash_size x hash_size`` corner (excluding the
    DC term at [0, 0], which just encodes overall brightness) is kept.
    """
    thumb_size = hash_size * highfreq_factor
    arr = _to_grayscale_array(image, (thumb_size, thumb_size))
    coeffs = dct2(arr)
    low_freq = coeffs[:hash_size, :hash_size].copy()
    # Exclude the DC coefficient: it only reflects average brightness, which
    # would otherwise dominate the median and make the hash overly sensitive
    # to exposure differences between otherwise-identical images.
    flat_without_dc = np.delete(low_freq.flatten(), 0)
    median = np.median(flat_without_dc)
    bits_grid = low_freq > median
    bits = _bits_from_bool_grid(bits_grid)
    return ImageHash("phash", bits, hash_size)


def wavelet_hash(image: Image.Image, hash_size: int = 8) -> ImageHash:
    """wHash: a simplified single-level Haar low-pass hash.

    Starts from a thumbnail sized to a power of two multiple of the hash
    size and repeatedly averages non-overlapping 2x2 blocks (the low-pass
    half of one level of a 2D Haar wavelet transform) until the grid matches
    ``hash_size``, then thresholds against the median.
    """
    thumb_size = hash_size * 4
    arr = _to_grayscale_array(image, (thumb_size, thumb_size))
    while arr.shape[0] > hash_size:
        h, w = arr.shape
        arr = arr.reshape(h // 2, 2, w // 2, 2).mean(axis=(1, 3))
    median = np.median(arr)
    bits = _bits_from_bool_grid(arr > median)
    return ImageHash("whash", bits, hash_size)


_ALGORITHM_FUNCS = {
    "ahash": average_hash,
    "dhash": difference_hash,
    "phash": perceptual_hash,
    "whash": wavelet_hash,
}


def compute_hash(image: Image.Image, algorithm: HashAlgorithm, hash_size: int = 8) -> ImageHash:
    """Dispatch to the requested hash algorithm."""
    try:
        func = _ALGORITHM_FUNCS[algorithm]
    except KeyError as exc:
        raise ValueError(f"unknown hash algorithm: {algorithm!r}") from exc
    return func(image, hash_size)


def compute_all_hashes(
    image: Image.Image, algorithms: tuple[HashAlgorithm, ...] = ALL_ALGORITHMS, hash_size: int = 8
) -> dict[HashAlgorithm, ImageHash]:
    """Compute every requested hash algorithm for a single image."""
    return {algo: compute_hash(image, algo, hash_size) for algo in algorithms}
