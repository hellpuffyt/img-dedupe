"""img-dedupe: find near-duplicate images by perceptual hash and cluster them.

This package never deletes anything on your behalf during a scan. It produces
a JSON review manifest that a human (or a script acting on human-approved
rules) can inspect, edit, and then feed to the ``apply`` command.
"""

from __future__ import annotations

__version__ = "0.1.0"
