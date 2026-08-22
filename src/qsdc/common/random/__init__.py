"""Random source constructors."""

from __future__ import annotations

from qsdc.common.random.base import RandomSource
from qsdc.common.random.classical import ClassicalRandomSource


def make_random_source(name: str, seed: int) -> RandomSource:
    if name == "classical":
        return ClassicalRandomSource(seed)
    if name == "sf-bs-qrng":
        from qsdc.common.random.sf_beamsplitter import SFBeamSplitterQRNG

        return SFBeamSplitterQRNG(seed=seed)
    raise ValueError(f"unknown random source {name!r}")
