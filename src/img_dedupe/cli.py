"""Command-line interface: ``img-dedupe scan`` and ``img-dedupe apply``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from img_dedupe.hashing import ALL_ALGORITHMS
from img_dedupe.manifest import ManifestError, apply_plan, build_apply_plan, load_manifest
from img_dedupe.metadata import DEFAULT_EXTENSIONS
from img_dedupe.scan import ScanSettings, build_manifest, run_scan
from img_dedupe.selection import DEFAULT_STRATEGY_ORDER, Strategy


def _parse_extensions(raw: str) -> tuple[str, ...]:
    exts = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if not part.startswith("."):
            part = f".{part}"
        exts.append(part.lower())
    return tuple(exts) or DEFAULT_EXTENSIONS


def _parse_strategy_order(raw: str) -> tuple[Strategy, ...]:
    valid = {"resolution", "file_size", "compression", "oldest", "newest"}
    order: list[Strategy] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if part not in valid:
            raise argparse.ArgumentTypeError(
                f"unknown strategy {part!r}; choose from {sorted(valid)}"
            )
        order.append(part)  # type: ignore[arg-type]
    if not order:
        raise argparse.ArgumentTypeError("strategy order must not be empty")
    return tuple(order)


def _cmd_scan(args: argparse.Namespace) -> int:
    root = Path(args.directory).resolve()
    if not root.exists():
        print(f"error: directory does not exist: {root}", file=sys.stderr)
        return 2

    settings = ScanSettings(
        root=root,
        recursive=args.recursive,
        extensions=_parse_extensions(args.extensions) if args.extensions else DEFAULT_EXTENSIONS,
        min_size=args.min_size,
        algorithm=args.algorithm,
        hash_size=args.hash_size,
        threshold=args.threshold,
        strategy_order=_parse_strategy_order(args.strategy_order)
        if args.strategy_order
        else DEFAULT_STRATEGY_ORDER,
    )
    report = run_scan(settings)
    manifest = build_manifest(report)

    output_path = Path(args.output)
    output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    summary = manifest["summary"]
    print(f"Scanned {summary['total_images']} image(s) under {root}")
    print(f"Found {summary['duplicate_groups']} duplicate group(s)")
    print(f"Reclaimable if all candidates removed: {summary['reclaimable_bytes']:,} bytes")
    print(f"Manifest written to {output_path}")
    return 0


def _cmd_apply(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    try:
        data = load_manifest(manifest_path)
    except (ManifestError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    trash_dir = Path(args.trash_dir).resolve() if args.trash_dir else None

    try:
        plan = build_apply_plan(data, trash_dir=trash_dir)
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if plan.skipped_groups:
        print(f"Skipped {len(plan.skipped_groups)} group(s) with nothing to remove")

    if not plan.actions:
        print("Nothing to do: no members marked 'delete_candidate'")
        return 0

    log = apply_plan(plan, execute=args.execute)
    for line in log:
        print(line)

    if not args.execute:
        print(f"\nDry run: {len(plan.actions)} file(s) would be affected. Re-run with --execute to apply.")
    else:
        print(f"\nApplied: {len(plan.actions)} file(s) affected.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="img-dedupe",
        description="Find near-duplicate images by perceptual hash and produce a review manifest.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="scan a directory and write a review manifest")
    scan_parser.add_argument("directory", help="directory to scan")
    scan_parser.add_argument(
        "-o", "--output", default="manifest.json", help="path to write the manifest JSON"
    )
    scan_parser.add_argument("--recursive", dest="recursive", action="store_true", default=True)
    scan_parser.add_argument("--no-recursive", dest="recursive", action="store_false")
    scan_parser.add_argument(
        "--extensions", default=None, help="comma-separated list of extensions, e.g. jpg,png"
    )
    scan_parser.add_argument("--min-size", type=int, default=0, help="minimum file size in bytes")
    scan_parser.add_argument(
        "--algorithm",
        choices=list(ALL_ALGORITHMS),
        default="phash",
        help="perceptual hash algorithm used for clustering",
    )
    scan_parser.add_argument("--hash-size", type=int, default=8, help="hash grid side length")
    scan_parser.add_argument(
        "--threshold", type=int, default=10, help="max Hamming distance to consider a near-duplicate"
    )
    scan_parser.add_argument(
        "--strategy-order",
        default=None,
        help="comma-separated best-copy strategy order, e.g. resolution,file_size,compression,oldest",
    )
    scan_parser.set_defaults(func=_cmd_scan)

    apply_parser = subparsers.add_parser("apply", help="apply a reviewed manifest")
    apply_parser.add_argument("manifest", help="path to a manifest JSON file")
    apply_parser.add_argument(
        "--trash-dir", default=None, help="move removed files here instead of deleting them"
    )
    apply_parser.add_argument(
        "--execute", action="store_true", help="actually perform the operations (default is dry run)"
    )
    apply_parser.set_defaults(func=_cmd_apply)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
