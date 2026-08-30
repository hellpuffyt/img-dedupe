# Contributing

Thanks for considering a contribution to img-dedupe.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

## Running the checks

The same checks run in CI, so run them locally before opening a pull request:

```bash
pytest
ruff check .
mypy
```

## Guidelines

- No binary test fixtures. Every test image is generated programmatically
  with Pillow inside the test suite (see `tests/imgen.py`).
- Keep the dependency list to Pillow and numpy. Do not add OpenCV or
  `imagehash` — implementing the hashing algorithms from scratch is the
  point of this project.
- The `scan` command must never delete or move a file. Only `apply`, acting
  on a manifest a human has reviewed, touches the filesystem.
- If you touch `hashing.py`'s DCT implementation, add or update a test that
  checks it against an independently computed reference value, not just
  against itself.
- Keep functions honest about what they measure: don't present a heuristic
  (like the bytes-per-pixel compression proxy) as an exact codec-level
  quality score.

## Reporting issues

Please include the img-dedupe version, Python version, operating system, and
a minimal reproduction (a script that generates the images that trigger the
issue is ideal, since no binary fixtures are needed).
