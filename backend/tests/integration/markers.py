"""Shared markers for integration tests."""

from pathlib import Path

import pytest

SAMPLE_GPX = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "samples"
    / "gpx"
    / "export-2025-08-01-16-35-30-1 Jasmer+Mamies.gpx"
)

# The sample GPX (third-party geocaching.com export) is not in the repo, so CI has no caches.
requires_sample_gpx = pytest.mark.skipif(
    not SAMPLE_GPX.exists(), reason="needs the sample GPX (data/samples/gpx), not in the repo"
)
