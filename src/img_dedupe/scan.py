"""End-to-end scan pipeline: discover images, hash them, cluster, classify,
select a best copy per group, and build a review manifest.

Nothing here deletes or moves a file. The output is a manifest dict, ready
to be written to JSON and reviewed by a human before ``apply`` acts on it.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from img_dedupe.classify import classify_pair, dominant_variant
from img_dedupe.cluster import cluster_by_distance
from img_dedupe.hashing import HashAlgorithm, ImageHash, compute_hash, hamming_distance
from img_dedupe.metadata import DEFAULT_EXTENSIONS, ImageMetadata, discover_images, read_metadata
from img_dedupe.selection import DEFAULT_STRATEGY_ORDER, Strategy, select_best

MANIFEST_VERSION = 1


@dataclass
class ScanSettings:
    root: Path
    recursive: bool = True
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS
    min_size: int = 0
    algorithm: HashAlgorithm = "phash"
    hash_size: int = 8
    threshold: int = 10
    strategy_order: tuple[Strategy, ...] = DEFAULT_STRATEGY_ORDER


@dataclass
class ScannedImage:
    metadata: ImageMetadata
    hashes: dict[HashAlgorithm, ImageHash]


@dataclass
class ScanReport:
    settings: ScanSettings
    images: list[ScannedImage] = field(default_factory=list)
    groups: list[list[int]] = field(default_factory=list)


def _load_scanned_image(path: Path, algorithms: tuple[HashAlgorithm, ...], hash_size: int) -> ScannedImage:
    metadata = read_metadata(path)
    with Image.open(path) as img:
        img.load()
        hashes = {algo: compute_hash(img, algo, hash_size) for algo in algorithms}
    return ScannedImage(metadata=metadata, hashes=hashes)


def run_scan(settings: ScanSettings, algorithms: tuple[HashAlgorithm, ...] | None = None) -> ScanReport:
    """Discover, hash, and cluster every image under ``settings.root``."""
    algos = algorithms or (settings.algorithm,)
    if settings.algorithm not in algos:
        algos = (*algos, settings.algorithm)

    paths = discover_images(
        settings.root,
        recursive=settings.recursive,
        extensions=settings.extensions,
        min_size=settings.min_size,
    )
    images = [_load_scanned_image(p, algos, settings.hash_size) for p in paths]

    def distance_fn(i: int, j: int) -> int:
        return hamming_distance(images[i].hashes[settings.algorithm], images[j].hashes[settings.algorithm])

    result = cluster_by_distance(len(images), distance_fn, settings.threshold)
    return ScanReport(settings=settings, images=images, groups=result.groups)


def build_manifest(report: ScanReport) -> dict[str, Any]:
    """Turn a :class:`ScanReport` into a JSON-serialisable review manifest."""
    settings = report.settings
    groups_out = []
    total_reclaimable = 0
    duplicate_groups = 0

    duplicate_index_groups = [g for g in report.groups if len(g) > 1]

    for group_id, member_indices in enumerate(duplicate_index_groups):
        members = [report.images[i] for i in member_indices]
        metadatas = [m.metadata for m in members]

        selection = select_best(metadatas, settings.strategy_order)
        kept_path = selection.best.path

        pairwise_kinds = []
        member_entries = []
        for scanned in members:
            meta = scanned.metadata
            distance_to_kept = (
                0
                if meta.path == kept_path
                else hamming_distance(
                    scanned.hashes[settings.algorithm],
                    next(m.hashes[settings.algorithm] for m in members if m.metadata.path == kept_path),
                )
            )
            kept_meta = selection.best
            variant = (
                "kept"
                if meta.path == kept_path
                else classify_pair(kept_meta, meta, distance_to_kept)
            )
            if variant != "kept":
                pairwise_kinds.append(variant)

            action = "keep" if meta.path == kept_path else "delete_candidate"
            member_entries.append(
                {
                    "path": str(meta.path),
                    "width": meta.width,
                    "height": meta.height,
                    "file_size": meta.file_size,
                    "sha256": meta.sha256,
                    "mtime": meta.mtime,
                    settings.algorithm: scanned.hashes[settings.algorithm].hex(),
                    "distance_to_kept": distance_to_kept,
                    "variant_vs_kept": variant,
                    "action": action,
                }
            )

        group_variant = dominant_variant(pairwise_kinds) if pairwise_kinds else "exact_duplicate"
        reclaimable = sum(m.file_size for m in metadatas if m.path != kept_path)
        total_reclaimable += reclaimable
        duplicate_groups += 1

        groups_out.append(
            {
                "group_id": group_id,
                "variant": group_variant,
                "reclaimable_bytes": reclaimable,
                "keep": {"path": str(kept_path), "reason": selection.reason},
                "members": member_entries,
            }
        )

    manifest: dict[str, Any] = {
        "version": MANIFEST_VERSION,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "root": str(settings.root),
        "settings": {
            "recursive": settings.recursive,
            "extensions": list(settings.extensions),
            "min_size": settings.min_size,
            "algorithm": settings.algorithm,
            "hash_size": settings.hash_size,
            "threshold": settings.threshold,
            "strategy_order": list(settings.strategy_order),
        },
        "summary": {
            "total_images": len(report.images),
            "duplicate_groups": duplicate_groups,
            "reclaimable_bytes": total_reclaimable,
        },
        "groups": groups_out,
    }
    return manifest
