# Production readiness — img-dedupe

Audit date: 2026-10-22. Tested commit: `d4479fc` (branch `audit/production-readiness`, based on `main` @ `9360301`).

## Scope

CLI + library: from-scratch perceptual hashes (aHash, dHash, pHash with an orthonormal DCT-II, wHash),
union-find clustering on Hamming distance, evidence-based keep selection, variant classification, a
JSON review manifest (`scan`, read-only), and `apply` (dry run by default; deletes or moves only with
`--execute`).

## Platforms

CPython 3.10+, Pillow ≥ 10, NumPy ≥ 1.24. Verified on macOS 27 (Apple M5), CPython 3.12.14.

## Deletion safety (owner requirement: never delete without an explicit flag)

- `scan` contains no file-mutating calls (only `manifest.py` calls `unlink`/`shutil.move`).
- `apply` without `--execute` only prints `WOULD ...` lines (test `test_apply_plan_dry_run_does_not_touch_filesystem`; clean-clone run: all four files untouched).
- New: removals are skipped when no kept member exists, when the candidate is the kept file, or when its sha256 changed; trash never overwrites.

## Clean-clone verification (commit `b47e699`, re-tested at `d4479fc` by test suite)

```bash
git clone -b audit/production-readiness <local clone> img-dedupe && cd img-dedupe
uv venv --python 3.12 .venv && . .venv/bin/activate && uv pip install -e .
# 4 synthetic images: original, 0.5x resize, JPEG q60 copy, unrelated
img-dedupe scan ./photos -o manifest.json      # 1 group, 58,276 bytes reclaimable
img-dedupe apply manifest.json                 # dry run, nothing touched
img-dedupe apply manifest.json --trash-dir ./_trash --execute   # 2 moved; orig + unrelated stay
uv pip install -e ".[dev]" && pytest && ruff check . && mypy    # 111 passed / clean / clean
```

## Commands and results

| Command | Baseline (`9360301`) | After (`d4479fc`) |
| --- | --- | --- |
| `pytest` | exit 0 — 105 passed, 0 failed, 0 skipped | exit 0 — 111 passed, 0 failed, 0 skipped |
| `ruff check .` / `mypy` | exit 0 / exit 0 | exit 0 / exit 0 |
| `uvx pip-audit` (Pillow, NumPy) | — | no known vulnerabilities |

CI status — default branch: success (`9360301`, 2026-08-30); audit branch: pending until pushed.

## Hash verification

DCT vs `scipy.fft.dctn(type=2, norm="ortho")`: max |diff| 3.0e-14. 40 synthetic smooth images ×
(0.5x resize, 2x upscale, JPEG q60): every algorithm max Hamming distance 2; unrelated pairs min 21
(aHash/dHash) / 24 (pHash/wHash). At the default threshold 10: recall 1.000, 0 false matches on this set.
Real photo libraries were not tested.

## Bugs found and fixed

| Severity | Bug (reproduced before fixing) | Regression test (`tests/test_manifest.py` unless noted) |
| --- | --- | --- |
| High (data loss) | `--trash-dir`: `a/photo.png` and `b/photo.png` in one group both moved to `trash/group_0/photo.png`; one image lost | `test_trash_never_overwrites_a_same_named_member` |
| High (data loss) | kept file moved away after scan → candidate still deleted (last copy) | `test_apply_skips_a_group_whose_kept_copy_is_gone` |
| Medium | candidate that is the kept file (symlink) or changed since scan was removed | `test_apply_skips_a_candidate_that_is_the_kept_file`, `test_apply_skips_a_file_changed_since_the_scan` |
| Low | summary reported planned actions as "affected" | `tests/test_cli.py::test_cli_apply_summary_counts_skipped_removals` |

Test change with justification: three existing apply tests referenced a `keep.png` that did not exist;
they now create it, since apply now (correctly) refuses to remove the only copy.

## Security review

No network. Manifest JSON is validated before use. Paths in a manifest are trusted input (the user
reviews it); apply only touches paths marked `delete_candidate`. History secret scan: no hits.
`pip-audit`: clean. Workflow permissions `contents: read`.

## Known limitations

- O(n²) pairwise comparison; Pillow decodes untrusted images (Pillow's own security posture applies).
- A manifest edited to point at arbitrary paths will act on them after review — by design.

## Acceptance checklist

| # | Item | Expected | Evidence | Result |
| --- | --- | --- | --- | --- |
| 1 | scan never modifies files | no mutation | code review + clean clone | PASS |
| 2 | apply is dry-run by default | nothing touched | test + clean clone | PASS |
| 3 | never empties a group / last copy | refused / skipped | tests | PASS |
| 4 | trash never overwrites | unique names | test | PASS |
| 5 | DCT correct | = SciPy | comparison | PASS |
| 6 | variants grouped, unrelated not | dist ≤ 2 vs ≥ 21 | measurement | PASS |
| 7 | clean clone | install/scan/apply/tests | above | PASS |

## Classification proposal

**Production-Ready for Its Documented Scope** (proposal), with real-photo-library accuracy unverified.
