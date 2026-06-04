"""Bit generation helpers."""

from __future__ import annotations

from utils.random.base import RandomSource


def weighted_random_bits(
    bit_count: int,
    one_probability: float,
    random_source: RandomSource,
) -> str:
    """Generate independent Bernoulli bits as a string."""

    if bit_count < 0:
        raise ValueError("bit_count must be non-negative")
    if not 0.0 <= one_probability <= 1.0:
        raise ValueError("one_probability must be between 0 and 1")
    return "".join(
        "1" if random_source.uniform(0.0, 1.0) < one_probability else "0"
        for _ in range(bit_count)
    )
