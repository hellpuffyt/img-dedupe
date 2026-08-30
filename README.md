# img-dedupe

Find near-duplicate images by perceptual hash, cluster them, and produce a
review manifest before anything is deleted.

## What

img-dedupe scans a directory of images, computes perceptual hashes for each
one, groups near-duplicates together, works out which copy in each group is
the "best" one to keep (on evidence, not luck), and writes a JSON manifest
describing every group, every member, and the proposed action. A separate
`apply` command then executes a manifest that a human has reviewed. The
`scan` command never deletes or moves a file.

## Why

Photo libraries and product-image catalogues accumulate resizes,
re-encodes, crops, and watermarked variants of the same picture over time.
Byte-level deduplication (matching on file hash) misses all of these,
because the bytes differ even though the picture is "the same" to a human.
Perceptual hashing finds them — but most tools that then delete on a
similarity threshold eventually delete the wrong thing. img-dedupe treats
review as a first-class step: it never deletes during a scan, it explains
why it picked the copy it picked, and `apply` refuses to remove every member
of a group.

## How perceptual hashing works here

Four algorithms are implemented from scratch on top of numpy and Pillow —
no OpenCV, no `imagehash` library:

- **aHash (average hash)** — shrink the image to an 8x8 greyscale
  thumbnail, take the mean brightness, and set one bit per pixel for
  "brighter than the mean". Cheap and fast, but sensitive to brightness/
  contrast changes.
- **dHash (difference hash)** — shrink to a 9x8 thumbnail and set one bit
  per pixel for "brighter than my right-hand neighbour". This encodes
  gradient direction rather than absolute brightness, so it's more robust
  to exposure changes than aHash.
- **pHash (perceptual hash)** — the technical centrepiece. Shrink to a
  32x32 greyscale thumbnail, take its 2D Discrete Cosine Transform (DCT-II),
  keep the low-frequency 8x8 corner (excluding the DC term, which only
  encodes overall brightness), and threshold against the median. Because it
  operates on frequency content rather than raw pixel values, pHash is the
  most robust of the four to re-encoding, mild resizing, and small colour
  shifts. The DCT itself is implemented directly from its definition as an
  orthonormal `N x N` basis matrix (`C[k, x] = alpha(k) * cos(pi/N * (x +
  0.5) * k)`), applied as `C @ image @ C.T` — no FFT trick, no scipy, and
  small enough to check by hand (see `tests/test_dct.py`).
- **wHash (wavelet hash)** — a simplified single-level Haar low-pass hash:
  repeatedly average non-overlapping 2x2 blocks of a thumbnail down to the
  target grid size, then threshold against the median.

Two hashes are compared with the **Hamming distance** (the number of
differing bits). Two hashes can only be compared if they come from the same
algorithm and the same grid size — comparing, say, an 8x8 pHash to a 4x4
aHash raises an error rather than returning a meaningless number.

## Features

- Four from-scratch perceptual hash algorithms (aHash, dHash, pHash, wHash).
- Union-find clustering over the pairwise-under-threshold similarity graph,
  so a chain of similar images (A close to B, B close to C) ends up in one
  group even if A and C aren't directly close.
- Evidence-based best-copy selection with a configurable strategy order:
  resolution, file size, compression (bytes-per-pixel proxy), and file age
  (oldest/newest). Every decision records *why* it was made, in terms of
  the actual values compared.
- Variant classification per pair: `exact_duplicate` (identical bytes),
  `re_encode` (same dimensions, different bytes), `resize` (same aspect
  ratio, different dimensions), `crop` (different aspect ratio).
- A JSON review manifest listing every group, every member's metrics, and
  the proposed action — nothing is deleted until `apply` is run against a
  manifest.
- `apply` refuses to remove every member of a group, and supports
  `--trash-dir` to move files instead of deleting them.
- Filters: `--min-size`, `--extensions`, `--recursive` / `--no-recursive`.
- Reports total reclaimable bytes.

## Architecture

```
src/img_dedupe/
  hashing.py    aHash, dHash, pHash (DCT-II from scratch), wHash, Hamming distance
  metadata.py   filesystem + image metadata, sha256, image discovery/filters
  cluster.py    union-find over a pairwise Hamming-distance graph
  classify.py   exact_duplicate / re_encode / resize / crop classification
  selection.py  configurable best-copy selection with recorded reasons
  scan.py       orchestrates discovery -> hashing -> clustering -> manifest
  manifest.py   manifest validation and the apply-time safety checks
  cli.py        `img-dedupe scan` / `img-dedupe apply`
```

## Installation

Requires Python 3.10+.

```bash
pip install -e .
```

Dependencies are intentionally minimal: `Pillow` and `numpy`.

## Usage

### Scan a directory

```bash
img-dedupe scan ./photos -o manifest.json
```

Useful options:

```bash
img-dedupe scan ./photos \
  --recursive \
  --extensions jpg,jpeg,png \
  --min-size 2048 \
  --algorithm phash \
  --threshold 10 \
  --strategy-order resolution,file_size,compression,oldest \
  -o manifest.json
```

- `--algorithm` — `ahash`, `dhash`, `phash` (default), or `whash`.
- `--threshold` — maximum Hamming distance (out of `hash_size^2` bits, 64 by
  default) for two images to be considered near-duplicates. Lower is
  stricter.
- `--strategy-order` — comma-separated best-copy strategy order, from
  `resolution`, `file_size`, `compression`, `oldest`, `newest`.

### Review the manifest

Open `manifest.json`. Each group lists every member with its metrics, which
one was chosen to `keep` and why, and each other member's proposed
`action` (`delete_candidate`). Edit `action` fields by hand if you disagree
with a proposal — set a member back to `"keep"` to preserve it.

### Apply a reviewed manifest

```bash
# Dry run (default): prints what would happen, touches nothing.
img-dedupe apply manifest.json

# Actually delete the delete_candidate files.
img-dedupe apply manifest.json --execute

# Move them to a trash directory instead of deleting.
img-dedupe apply manifest.json --trash-dir ./_trash --execute
```

`apply` validates the manifest and refuses to run if any group would have
every member removed — at least one member per group must be kept.

## Safety model

- `scan` **never** deletes or moves a file. It only reads images and writes
  a manifest.
- `apply` defaults to a dry run; nothing is touched without `--execute`.
- `apply` refuses to process a group where every member is marked
  `delete_candidate` — a manifest hand-edited (or generated) that way is
  rejected outright, before any file operation runs.
- `--trash-dir` moves files instead of deleting them, so removals can be
  undone by hand.
- A missing file referenced by the manifest is skipped, not treated as an
  error — the manifest may be stale if files moved between `scan` and
  `apply`.

## Manifest format

```json
{
  "version": 1,
  "generated_at": "2026-08-30T12:00:00+00:00",
  "root": "/path/to/photos",
  "settings": {
    "recursive": true,
    "extensions": [".png", ".jpg"],
    "min_size": 0,
    "algorithm": "phash",
    "hash_size": 8,
    "threshold": 10,
    "strategy_order": ["resolution", "file_size", "compression", "oldest"]
  },
  "summary": {
    "total_images": 5,
    "duplicate_groups": 1,
    "reclaimable_bytes": 8724
  },
  "groups": [
    {
      "group_id": 0,
      "variant": "re_encode",
      "reclaimable_bytes": 8724,
      "keep": {
        "path": "/path/to/photos/photo1.jpg",
        "reason": "photo1.jpg kept over photo1_small.png: higher resolution (90000.0 vs 22500.0 pixels)"
      },
      "members": [
        {
          "path": "/path/to/photos/photo1.jpg",
          "width": 300,
          "height": 300,
          "file_size": 5558,
          "sha256": "...",
          "mtime": 1788108047.94,
          "phash": "d5d51daaaaaa82d1",
          "distance_to_kept": 0,
          "variant_vs_kept": "kept",
          "action": "keep"
        },
        {
          "path": "/path/to/photos/photo1_small.png",
          "...": "...",
          "variant_vs_kept": "resize",
          "action": "delete_candidate"
        }
      ]
    }
  ]
}
```

Only groups with more than one member appear in `groups`; unique images are
counted in `summary.total_images` but not otherwise listed.

## Examples

Find and review duplicates in a photo library, keeping the newest copy of
each group instead of the default (highest resolution first):

```bash
img-dedupe scan ~/Pictures --recursive --strategy-order newest,resolution,file_size -o review.json
# ... inspect/edit review.json ...
img-dedupe apply review.json --trash-dir ~/Pictures/_dedupe_trash --execute
```

Only consider large JPEGs, with a tight similarity threshold:

```bash
img-dedupe scan ./catalogue --extensions jpg,jpeg --min-size 100000 --threshold 6 -o manifest.json
```

## Testing

```bash
pip install -e ".[dev]"
pytest
ruff check .
mypy
```

The test suite generates every test image programmatically with Pillow — no
binary fixtures are committed. Coverage includes: DCT correctness against an
independently computed reference, hash stability under small quality
changes and instability across genuinely different content, union-find
chaining, best-copy selection for every strategy, variant classification,
and `apply`'s refusal to empty a group.

## Limitations

- The "compression" selection strategy is a bytes-per-pixel proxy, not a
  true measurement of a specific codec's quality setting — it's a
  reproducible signal, not an exact one.
- Clustering is O(n^2) in the number of images (every pair is compared).
  This is the right trade-off for a batch, review-before-delete workflow,
  but it is not built for millions of images in one scan.
- Crop detection relies on aspect ratio and hash distance; it will not
  reliably detect crops with a preserved aspect ratio (those look like a
  resize) or extreme crops that fall outside the similarity threshold.
- Rotation and mirroring are not specifically modelled; rotated/flipped
  duplicates will generally not be clustered together by these hashes.

## Security

- img-dedupe only reads files under the directory you point it at (plus the
  manifest file you pass to `apply`) and only writes the manifest file and,
  during `apply`, the files it is told to delete or move.
- `apply` never deletes a path outside what the manifest lists, and never
  empties a group of every member.
- No network access is performed by any part of this tool.

## License

MIT. See [LICENSE](LICENSE).
