"""Pick the "best" copy to keep within a group of near-duplicates.

Selection is a configurable ordered list of strategies, each a comparator
that ranks images from best to worst. The first strategy that distinguishes
two images decides between them; ties fall through to the next strategy.
Every decision records *why* it was made, in terms of the actual metadata
values compared -- not just "this one won".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from img_dedupe.metadata import ImageMetadata

Strategy = Literal["resolution", "file_size", "compression", "oldest", "newest"]

DEFAULT_STRATEGY_ORDER: tuple[Strategy, ...] = (
    "resolution",
    "file_size",
    "compression",
    "oldest",
)


def _key_resolution(m: ImageMetadata) -> float:
    return float(m.pixel_count)


def _key_file_size(m: ImageMetadata) -> float:
    return float(m.file_size)


def _key_compression(m: ImageMetadata) -> float:
    # Higher bytes-per-pixel implies lighter compression; prefer higher.
    return m.bytes_per_pixel


def _key_oldest(m: ImageMetadata) -> float:
    # Older files have a smaller mtime; to rank "best first" as "larger key
    # first" consistently, invert so an older mtime produces a larger key.
    return -m.mtime


def _key_newest(m: ImageMetadata) -> float:
    return m.mtime


_STRATEGY_KEYS = {
    "resolution": _key_resolution,
    "file_size": _key_file_size,
    "compression": _key_compression,
    "oldest": _key_oldest,
    "newest": _key_newest,
}

_STRATEGY_LABELS = {
    "resolution": "higher resolution ({0} vs {1} pixels)",
    "file_size": "larger file size ({0} vs {1} bytes)",
    "compression": "less compressed ({0:.3f} vs {1:.3f} bytes/pixel)",
    "oldest": "older file (mtime {0} vs {1})",
    "newest": "newer file (mtime {0} vs {1})",
}


@dataclass(frozen=True)
class SelectionResult:
    """The outcome of choosing a best copy within a group."""

    best: ImageMetadata
    reason: str


def select_best(
    members: list[ImageMetadata],
    strategy_order: tuple[Strategy, ...] = DEFAULT_STRATEGY_ORDER,
) -> SelectionResult:
    """Choose the best copy among ``members`` using ``strategy_order``.

    Raises ``ValueError`` if ``members`` is empty.
    """
    if not members:
        raise ValueError("cannot select a best copy from an empty group")
    if len(members) == 1:
        return SelectionResult(best=members[0], reason="only member of the group")

    current_best = members[0]
    reason = "first candidate (no other members compared yet)"
    for candidate in members[1:]:
        winner, why = _compare(current_best, candidate, strategy_order)
        current_best = winner
        reason = why
    return SelectionResult(best=current_best, reason=reason)


def _compare(
    a: ImageMetadata, b: ImageMetadata, strategy_order: tuple[Strategy, ...]
) -> tuple[ImageMetadata, str]:
    """Compare two candidates strategy by strategy; return the winner and why."""
    for strategy in strategy_order:
        key_fn = _STRATEGY_KEYS[strategy]
        key_a, key_b = key_fn(a), key_fn(b)
        if key_a == key_b:
            continue
        winner, loser = (a, b) if key_a > key_b else (b, a)
        winner_val, loser_val = (key_a, key_b) if key_a > key_b else (key_b, key_a)
        label = _STRATEGY_LABELS[strategy]
        reason = f"{winner.path.name} kept over {loser.path.name}: {label.format(winner_val, loser_val)}"
        return winner, reason
    # Every strategy tied: fall back to a stable, deterministic choice.
    winner, loser = (a, b) if str(a.path) <= str(b.path) else (b, a)
    reason = (
        f"{winner.path.name} kept over {loser.path.name}: "
        "all configured strategies tied; kept lexicographically first path for determinism"
    )
    return winner, reason
