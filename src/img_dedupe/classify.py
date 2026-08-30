"""Classify what kind of variant one image is relative to another.

The classification is evidence-based, not similarity-score-based: it looks
at exact byte identity, decoded dimensions and aspect ratio -- things read
directly from the files -- and only falls back to the perceptual distance
that put the pair in the same cluster in the first place.
"""

from __future__ import annotations

from typing import Literal

from img_dedupe.metadata import ImageMetadata

VariantKind = Literal["exact_duplicate", "re_encode", "resize", "crop", "similar"]

# Aspect ratios within this relative tolerance are considered "the same"
# (rounding noise from resizing algorithms, not a genuine crop).
ASPECT_RATIO_TOLERANCE = 0.02


def classify_pair(a: ImageMetadata, b: ImageMetadata, hash_distance: int) -> VariantKind:
    """Classify the relationship between two images already known to be
    in the same near-duplicate cluster (i.e. ``hash_distance`` is already
    at or under the clustering threshold)."""
    if a.sha256 == b.sha256:
        return "exact_duplicate"

    same_dimensions = a.width == b.width and a.height == b.height
    if same_dimensions:
        return "re_encode"

    ratio_a, ratio_b = a.aspect_ratio, b.aspect_ratio
    if ratio_a == 0 or ratio_b == 0:
        return "similar"
    relative_diff = abs(ratio_a - ratio_b) / max(ratio_a, ratio_b)
    if relative_diff <= ASPECT_RATIO_TOLERANCE:
        return "resize"

    # Different aspect ratio but still perceptually close enough to be
    # clustered together: consistent with one being a crop of the other.
    return "crop"


def dominant_variant(kinds: list[VariantKind]) -> VariantKind:
    """Pick one label to summarise a whole group from its pairwise labels.

    Priority favours the most specific/actionable classification: exact
    duplicates first (cheapest, safest to resolve), then re-encodes, then
    resizes, then crops, and "similar" only if nothing more specific applied.
    """
    priority: tuple[VariantKind, ...] = (
        "exact_duplicate",
        "re_encode",
        "resize",
        "crop",
        "similar",
    )
    present = set(kinds)
    for kind in priority:
        if kind in present:
            return kind
    return "similar"
