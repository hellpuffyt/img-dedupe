from __future__ import annotations

from pathlib import Path

import pytest

from img_dedupe.metadata import ImageMetadata
from img_dedupe.selection import select_best


def _meta(name: str, **overrides: object) -> ImageMetadata:
    defaults: dict[str, object] = dict(
        path=Path(name),
        file_size=1000,
        width=100,
        height=100,
        mode="RGB",
        format="PNG",
        mtime=1000.0,
        sha256=name,
    )
    defaults.update(overrides)
    return ImageMetadata(**defaults)  # type: ignore[arg-type]


def test_select_best_empty_raises() -> None:
    with pytest.raises(ValueError):
        select_best([])


def test_select_best_single_member() -> None:
    m = _meta("only.png")
    result = select_best([m])
    assert result.best is m
    assert "only member" in result.reason


def test_resolution_strategy_prefers_more_pixels() -> None:
    small = _meta("small.png", width=100, height=100)
    big = _meta("big.png", width=400, height=400)
    result = select_best([small, big], strategy_order=("resolution",))
    assert result.best is big
    assert "resolution" in result.reason or "pixels" in result.reason


def test_file_size_strategy_prefers_larger_file() -> None:
    a = _meta("a.png", width=100, height=100, file_size=500)
    b = _meta("b.png", width=100, height=100, file_size=5000)
    result = select_best([a, b], strategy_order=("file_size",))
    assert result.best is b


def test_compression_strategy_prefers_more_bytes_per_pixel() -> None:
    lightly_compressed = _meta("light.png", width=100, height=100, file_size=9000)
    heavily_compressed = _meta("heavy.png", width=100, height=100, file_size=500)
    result = select_best([lightly_compressed, heavily_compressed], strategy_order=("compression",))
    assert result.best is lightly_compressed


def test_oldest_strategy_prefers_smaller_mtime() -> None:
    older = _meta("old.png", mtime=100.0)
    newer = _meta("new.png", mtime=99999.0)
    result = select_best([older, newer], strategy_order=("oldest",))
    assert result.best is older


def test_newest_strategy_prefers_larger_mtime() -> None:
    older = _meta("old.png", mtime=100.0)
    newer = _meta("new.png", mtime=99999.0)
    result = select_best([older, newer], strategy_order=("newest",))
    assert result.best is newer


def test_strategy_order_falls_through_on_tie() -> None:
    # Same resolution -> tie -> fall through to file_size.
    a = _meta("a.png", width=100, height=100, file_size=1000)
    b = _meta("b.png", width=100, height=100, file_size=9000)
    result = select_best([a, b], strategy_order=("resolution", "file_size"))
    assert result.best is b


def test_all_strategies_tie_falls_back_to_deterministic_path_order() -> None:
    a = _meta("a.png", width=100, height=100, file_size=1000, mtime=1.0)
    b = _meta("b.png", width=100, height=100, file_size=1000, mtime=1.0)
    result = select_best([a, b], strategy_order=("resolution", "file_size", "compression", "oldest"))
    # "a.png" sorts before "b.png" lexicographically.
    assert result.best is a
    assert "tied" in result.reason


def test_select_best_among_three_members_full_default_order() -> None:
    lowres = _meta("lowres.png", width=50, height=50, file_size=2000, mtime=5.0)
    highres_small_file = _meta("highres_small.png", width=800, height=800, file_size=1500, mtime=3.0)
    highres_big_file = _meta("highres_big.png", width=800, height=800, file_size=50000, mtime=1.0)
    result = select_best([lowres, highres_small_file, highres_big_file])
    assert result.best is highres_big_file


def test_reason_mentions_both_filenames() -> None:
    small = _meta("small.png", width=100, height=100)
    big = _meta("big.png", width=400, height=400)
    result = select_best([small, big], strategy_order=("resolution",))
    assert "small.png" in result.reason
    assert "big.png" in result.reason
