"""Gaussian interval mapping utilities."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import NormalDist

from qsdc.common.random.base import RandomSource


@dataclass(frozen=True)
class GaussianInterval:
    symbol: str
    lower: float
    upper: float
    probability_lower: float
    probability_upper: float

    def contains(self, value: float) -> bool:
        return self.lower <= value < self.upper


def interval_count(box_bit_length: int) -> int:
    if box_bit_length < 1:
        raise ValueError("box_bit_length must be positive")
    return 2**box_bit_length


def gaussian_distribution(variance: float) -> NormalDist:
    if variance <= 0:
        raise ValueError("variance must be positive")
    return NormalDist(mu=0.0, sigma=sqrt(variance))


def equal_probability_intervals(
    box_bit_length: int,
    variance: float,
) -> tuple[GaussianInterval, ...]:
    distribution = gaussian_distribution(variance)
    count = interval_count(box_bit_length)
    intervals: list[GaussianInterval] = []

    for index in range(count):
        probability_lower = index / count
        probability_upper = (index + 1) / count
        lower = (
            float("-inf")
            if index == 0
            else distribution.inv_cdf(probability_lower)
        )
        upper = (
            float("inf")
            if index == count - 1
            else distribution.inv_cdf(probability_upper)
        )
        intervals.append(
            GaussianInterval(
                symbol=format(index, f"0{box_bit_length}b"),
                lower=lower,
                upper=upper,
                probability_lower=probability_lower,
                probability_upper=probability_upper,
            )
        )

    return tuple(intervals)


def interval_for_symbol(
    symbol: str,
    intervals: tuple[GaussianInterval, ...],
) -> GaussianInterval:
    for interval in intervals:
        if interval.symbol == symbol:
            return interval
    raise ValueError(f"unknown mapping symbol {symbol!r}")


def symbol_for_value(
    value: float,
    intervals: tuple[GaussianInterval, ...],
) -> str:
    for interval in intervals:
        if interval.contains(value):
            return interval.symbol
    if value == float("inf"):
        return intervals[-1].symbol
    raise ValueError(f"value {value!r} does not lie in any interval")


def sample_from_interval(
    interval: GaussianInterval,
    variance: float,
    random_source: RandomSource,
) -> float:
    distribution = gaussian_distribution(variance)
    probability = random_source.uniform(
        interval.probability_lower,
        interval.probability_upper,
    )
    probability = min(max(probability, 1e-15), 1.0 - 1e-15)
    return distribution.inv_cdf(probability)


def sample_gaussian(variance: float, random_source: RandomSource) -> float:
    distribution = gaussian_distribution(variance)
    probability = random_source.uniform(1e-15, 1.0 - 1e-15)
    return distribution.inv_cdf(probability)
