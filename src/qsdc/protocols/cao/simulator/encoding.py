"""Paper-style bit uniformization helpers."""

from __future__ import annotations

from math import inf, sqrt
from statistics import NormalDist

from qsdc.common import gaussian
from qsdc.common.random.base import RandomSource


def gaussian_encoding(
    box_bit_length: int,
    variance: float,
) -> gaussian.GaussianEncoding:
    symbol_count = 2**box_bit_length
    bit_labels = [
        f"{symbol_index:0{box_bit_length}b}"
        for symbol_index in range(symbol_count)
    ]
    return gaussian.get_gaussian_encoding(bit_labels, variance=variance)


def interval_for_bits(
    bits: str,
    encoding: gaussian.GaussianEncoding,
) -> gaussian.EncodingInterval:
    for interval in encoding.intervals:
        if interval.bits == bits:
            return interval
    raise ValueError(f"unknown encoding symbol {bits!r}")


def bits_for_real(value: float, encoding: gaussian.GaussianEncoding) -> str:
    for interval in encoding.intervals:
        if interval.contains(value):
            return interval.bits
    if value == inf:
        return encoding.intervals[-1].bits
    raise ValueError(
        f"value {value!r} was not found in any encoding interval; "
        "review the interval configuration"
    )


def sample_gaussian(variance: float, random_source: RandomSource) -> float:
    distribution = NormalDist(mu=0.0, sigma=sqrt(variance))
    probability = random_source.uniform(1e-15, 1.0 - 1e-15)
    return distribution.inv_cdf(probability)


def sample_gaussian_from_interval(
    interval: gaussian.EncodingInterval,
    variance: float,
    random_source: RandomSource,
) -> float:
    distribution = NormalDist(mu=0.0, sigma=sqrt(variance))
    probability = random_source.uniform(
        distribution.cdf(interval.lower),
        distribution.cdf(interval.upper),
    )
    probability = min(max(probability, 1e-15), 1.0 - 1e-15)
    return distribution.inv_cdf(probability)


def uniformize_message_bits(bits: str, random_source: RandomSource) -> str:
    mapping = {
        "0": ("01", "10"),
        "1": ("00", "11"),
    }
    return "".join(random_source.choice(mapping[bit]) for bit in bits)


def uniformize_block_bits(bits: str, random_source: RandomSource) -> str:
    mapping = {
        "0": ("00", "01"),
        "1": ("10", "11"),
    }
    return "".join(random_source.choice(mapping[bit]) for bit in bits)
