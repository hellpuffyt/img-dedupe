"""Filesystem and image metadata used as the evidence for every decision.

Nothing in this module guesses. Every field is either read directly from the
filesystem, computed by hashing the file's exact bytes, or read from the
decoded image via Pillow.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

DEFAULT_EXTENSIONS: tuple[str, ...] = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tiff")


@dataclass(frozen=True)
class ImageMetadata:
    """Evidence gathered about one image file."""

    path: Path
    file_size: int
    width: int
    height: int
    mode: str
    format: str | None
    mtime: float
    sha256: str

    @property
    def pixel_count(self) -> int:
        return self.width * self.height

    @property
    def aspect_ratio(self) -> float:
        if self.height == 0:
            return 0.0
        return self.width / self.height

    @property
    def bytes_per_pixel(self) -> float:
        """A cheap proxy for compression level: more bytes per pixel means less
        compression was applied (a rough, but real and reproducible, signal --
        not a guess about a specific codec's quality setting)."""
        if self.pixel_count == 0:
            return 0.0
        return self.file_size / self.pixel_count


def sha256_of_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Hash a file's exact bytes. Used to detect byte-identical duplicates."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_metadata(path: Path) -> ImageMetadata:
    """Read filesystem stats and decode image dimensions for one file."""
    stat = path.stat()
    with Image.open(path) as img:
        img.load()
        width, height = img.size
        mode = img.mode
        fmt = img.format
    return ImageMetadata(
        path=path,
        file_size=stat.st_size,
        width=width,
        height=height,
        mode=mode,
        format=fmt,
        mtime=stat.st_mtime,
        sha256=sha256_of_file(path),
    )


def discover_images(
    root: Path,
    recursive: bool = True,
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS,
    min_size: int = 0,
) -> list[Path]:
    """Find candidate image files under ``root``.

    ``extensions`` is matched case-insensitively. ``min_size`` filters out
    files smaller than the given number of bytes (e.g. tiny icons/spacers).
    """
    normalized_exts = {ext.lower() for ext in extensions}
    pattern = "**/*" if recursive else "*"
    results: list[Path] = []
    for candidate in sorted(root.glob(pattern)):
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() not in normalized_exts:
            continue
        if candidate.stat().st_size < min_size:
            continue
        results.append(candidate)
    return results
