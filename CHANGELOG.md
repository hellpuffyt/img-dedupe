# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed (data loss in `apply --execute`)

- A group was applied even when its kept file had been moved or deleted since
  the scan, removing the last remaining copy. Such groups are now skipped.
- `--trash-dir` moved same-named members of one group (`a/photo.png`,
  `b/photo.png`) to the same trash path, so the second overwrote the first.
  Trash names are now made unique.
- A candidate that is the same file as a kept member (e.g. via a symlink), or
  whose bytes changed since the scan (recorded `sha256`), is now skipped.

### Changed

- Three existing apply tests created no kept file; they now create one (the
  behaviour they test is unchanged; without it apply now refuses, by design).
- README: install from source; apply-time safety checks and hash verification
  documented. Added `SECURITY.md`, `.editorconfig`, `docs/PRODUCTION_READINESS.md`.

## [0.1.0] - 2026-08-30

### Added

- Four perceptual hash algorithms implemented from scratch on numpy + Pillow:
  aHash, dHash, pHash (with a hand-rolled orthonormal DCT-II), and wHash.
- Union-find clustering of near-duplicate images by Hamming distance, with
  chaining through intermediate images.
- Evidence-based "best copy" selection with a configurable strategy order
  (resolution, file size, compression, oldest/newest) and a human-readable
  reason for every decision.
- Variant classification: exact duplicate, re-encode, resize, crop.
- `img-dedupe scan`: discovers images, hashes and clusters them, and writes a
  JSON review manifest. Never deletes or moves anything.
- `img-dedupe apply`: executes a reviewed manifest, with dry-run by default,
  `--trash-dir` to move instead of delete, and a hard refusal to empty an
  entire group of its members.
- 105 pytest tests, all images generated programmatically at test time.
