"""Shared utilities for QSDC simulators."""

from utils.bits.comparison import hamming_distance
from utils.bits.conversion import bits_to_bytes, bytes_to_bits, chunk_bits
from utils.bits.generation import weighted_random_bits
from utils.random.base import RandomSource
from utils.random.classical import ClassicalRandomSource
from utils.random.sf_bs import SFBeamSplitterQRNG


def make_random_source(name: str, seed: int) -> RandomSource:
    if name == "classical":
        return ClassicalRandomSource(seed)
    if name == "sf-bs-qrng":
        return SFBeamSplitterQRNG(seed=seed)
    raise ValueError(f"unknown random source {name!r}")


__all__ = [
    "ClassicalRandomSource",
    "RandomSource",
    "SFBeamSplitterQRNG",
    "bits_to_bytes",
    "bytes_to_bits",
    "chunk_bits",
    "hamming_distance",
    "make_random_source",
    "weighted_random_bits",
]
