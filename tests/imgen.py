"""Programmatic test-image generators used across the test suite.

No binary fixtures are committed; every image used in a test is built here
with Pillow at test time.
"""

from __future__ import annotations

import io
import random
from pathlib import Path

from PIL import Image, ImageDraw


def solid_color_image(
    size: tuple[int, int] = (256, 256), color: tuple[int, int, int] = (200, 60, 60)
) -> Image.Image:
    return Image.new("RGB", size, color)


def noise_image(size: tuple[int, int] = (256, 256), seed: int = 0) -> Image.Image:
    rng = random.Random(seed)
    img = Image.new("RGB", size)
    pixels = [
        (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255)) for _ in range(size[0] * size[1])
    ]
    img.putdata(pixels)
    return img


def pattern_image(size: tuple[int, int] = (256, 256), seed: int = 0) -> Image.Image:
    """A structured (non-random, non-solid) image: shapes on a gradient
    background, so pHash/dHash/aHash all have real structure to hash."""
    rng = random.Random(seed)
    img = Image.new("RGB", size, (255, 255, 255))
    px = img.load()
    for y in range(size[1]):
        shade = int(255 * y / max(1, size[1] - 1))
        for x in range(size[0]):
            px[x, y] = (shade, 255 - shade, (shade * 7) % 256)

    draw = ImageDraw.Draw(img)
    max_w = max(2, size[0] // 3)
    max_h = max(2, size[1] // 3)
    for _ in range(8):
        x0 = rng.randint(0, size[0] - 1)
        y0 = rng.randint(0, size[1] - 1)
        w = rng.randint(1, max_w)
        h = rng.randint(1, max_h)
        color = (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
        shape = rng.choice(["rect", "ellipse"])
        box = [x0, y0, min(size[0] - 1, x0 + w), min(size[1] - 1, y0 + h)]
        if shape == "rect":
            draw.rectangle(box, fill=color)
        else:
            draw.ellipse(box, fill=color)
    return img


def save(img: Image.Image, path: Path, fmt: str = "PNG", quality: int | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    save_kwargs = {}
    if quality is not None:
        save_kwargs["quality"] = quality
    img.save(path, format=fmt, **save_kwargs)
    return path


def reencode_bytes(img: Image.Image, fmt: str = "JPEG", quality: int = 50) -> bytes:
    """Re-encode an image in memory and return the resulting bytes, without
    touching disk -- used to prove two saves of the same pixels differ in
    bytes but keep the same dimensions."""
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=quality)
    return buf.getvalue()


def resized(img: Image.Image, scale: float) -> Image.Image:
    w, h = img.size
    new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
    return img.resize(new_size, Image.Resampling.LANCZOS)


def cropped(img: Image.Image, fraction: float = 0.7) -> Image.Image:
    w, h = img.size
    new_w, new_h = int(w * fraction), int(h * fraction)
    left = (w - new_w) // 2
    top = (h - new_h) // 2
    return img.crop((left, top, left + new_w, top + new_h))
