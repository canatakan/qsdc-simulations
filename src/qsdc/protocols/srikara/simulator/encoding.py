"""Alice's 3-bit symbols as real message values m_A, displaced by beta_A = m_A (1 + i)."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from math import inf, sqrt
from statistics import NormalDist

from qsdc.common.random.base import RandomSource

MESSAGE_DIRECTION = 1 + 1j


@dataclass(frozen=True)
class IntervalCode:
    """Eight labelled intervals of the real line; the unbounded outer ones are sampled over tail_width."""

    labels: tuple[str, ...]
    bounds: tuple[float, ...]
    tail_width: float

    def interval(self, bits: str) -> tuple[float, float]:
        index = self.labels.index(bits)
        return self.bounds[index], self.bounds[index + 1]

    def sample(self, bits: str, rng: RandomSource) -> float:
        lower, upper = self.interval(bits)
        if lower == -inf:
            lower = upper - self.tail_width
        if upper == inf:
            upper = lower + self.tail_width
        return rng.uniform(lower, upper)

    def decode(self, value: float) -> str:
        return self.labels[bisect_right(self.bounds, value) - 1]


def gaussian_code(variance: float) -> IntervalCode:
    """Gray-coded, equiprobable intervals of N(0, variance), as in Cao et al.'s Gaussian mapping.

    Cao et al. use the outer interval [3.25, 7] for variance 8; the tail width scales with sigma.
    """
    gaussian = NormalDist(0.0, sqrt(variance))
    bounds = (-inf, *(gaussian.inv_cdf(i / 8) for i in range(1, 8)), inf)
    labels = ("000", "001", "011", "010", "110", "100", "101", "111")
    return IntervalCode(labels, bounds, tail_width=3.75 * sqrt(variance / 8.0))


INTERVAL_CODES = {
    "default": IntervalCode(
        labels=("000", "001", "010", "011", "100", "101", "110", "111"),
        bounds=(-inf, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, inf),
        tail_width=1.0,
    ),
    "optimized_v4": gaussian_code(4.0),
    "optimized_v8": gaussian_code(8.0),
    "optimized_v12": gaussian_code(12.0),
}
