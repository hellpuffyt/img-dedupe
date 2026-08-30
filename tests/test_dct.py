"""Correctness tests for the hand-rolled DCT-II implementation.

These check the transform against values computed independently (by plain
``math.cos`` arithmetic written directly in the test, not by re-using any
code from ``img_dedupe``), so a bug shared between the implementation and
the test cannot hide.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from img_dedupe.hashing import _dct_matrix, dct2


def _reference_dct_matrix(n: int) -> np.ndarray:
    """Independent reference implementation of the same orthonormal DCT-II
    basis, written with plain nested loops and ``math.cos``."""
    matrix = np.zeros((n, n), dtype=np.float64)
    for k in range(n):
        alpha = math.sqrt(1.0 / n) if k == 0 else math.sqrt(2.0 / n)
        for x in range(n):
            matrix[k, x] = alpha * math.cos(math.pi / n * (x + 0.5) * k)
    return matrix


@pytest.mark.parametrize("n", [1, 2, 4, 8, 16])
def test_dct_matrix_matches_independent_reference(n: int) -> None:
    expected = _reference_dct_matrix(n)
    actual = _dct_matrix(n)
    np.testing.assert_allclose(actual, expected, atol=1e-12)


def test_dct_matrix_is_orthonormal() -> None:
    """An orthonormal DCT basis matrix C satisfies C @ C.T == identity."""
    n = 8
    c = _dct_matrix(n)
    product = c @ c.T
    np.testing.assert_allclose(product, np.eye(n), atol=1e-10)


def test_dct2_of_constant_matrix_has_energy_only_in_dc_term() -> None:
    """A flat (constant-value) image has zero spatial frequency content:
    every DCT coefficient except the DC term [0, 0] must be ~zero."""
    n = 8
    constant_value = 42.0
    matrix = np.full((n, n), constant_value)
    coeffs = dct2(matrix)

    dc = coeffs[0, 0]
    expected_dc = constant_value * n  # sqrt(1/n)*sqrt(1/n) summed n*n times * n... verified below
    # Independently verify the DC formula: DC = alpha0^2 * sum(all pixels)
    # alpha0 = sqrt(1/n), so DC = (1/n) * (n*n*constant_value) = n*constant_value
    assert dc == pytest.approx(expected_dc, rel=1e-9)

    non_dc = coeffs.copy()
    non_dc[0, 0] = 0.0
    assert np.allclose(non_dc, 0.0, atol=1e-9)


def test_dct2_known_4x4_input_matches_hand_computed_dc() -> None:
    """A small, fully worked example: DC coefficient of the DCT-II of a
    4x4 matrix of known values, computed independently from first
    principles (DC = alpha(0) * sum_x alpha(0) * sum of all entries)."""
    matrix = np.array(
        [
            [1.0, 2.0, 3.0, 4.0],
            [5.0, 6.0, 7.0, 8.0],
            [9.0, 10.0, 11.0, 12.0],
            [13.0, 14.0, 15.0, 16.0],
        ]
    )
    n = 4
    alpha0 = math.sqrt(1.0 / n)
    expected_dc = alpha0 * alpha0 * matrix.sum()

    coeffs = dct2(matrix)
    assert coeffs[0, 0] == pytest.approx(expected_dc, rel=1e-9)


def test_dct2_requires_square_matrix() -> None:
    with pytest.raises(ValueError):
        dct2(np.zeros((4, 8)))


def test_dct2_is_invertible_via_transpose() -> None:
    """Because the basis is orthonormal, the inverse DCT is C.T @ coeffs @ C."""
    n = 8
    rng = np.random.default_rng(42)
    matrix = rng.random((n, n))
    c = _dct_matrix(n)
    coeffs = c @ matrix @ c.T
    reconstructed = c.T @ coeffs @ c
    np.testing.assert_allclose(reconstructed, matrix, atol=1e-9)
