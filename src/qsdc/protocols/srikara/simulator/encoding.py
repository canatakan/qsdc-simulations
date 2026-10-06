"""Alice's 3-bit symbols as real message values m_A, displaced by beta_A = m_A (1 + i)."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, replace
from math import inf, sqrt
from statistics import NormalDist

from qsdc.common.quadrature import VACUUM_VARIANCE
from qsdc.common.random.base import RandomSource

MESSAGE_DIRECTION = 1 + 1j
# Neighbouring intervals differ in one bit, so a small error costs one bit.
GRAY_LABELS = ("000", "001", "011", "010", "110", "100", "101", "111")


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

    @property
    def energy_snu(self) -> float:
        """Mean m_A^2 of equiprobable symbols, in shot-noise units."""
        total = 0.0
        for bits in self.labels:
            lower, upper = self.interval(bits)
            lower = upper - self.tail_width if lower == -inf else lower
            upper = lower + self.tail_width if upper == inf else upper
            total += (lower**2 + lower * upper + upper**2) / 3
        return total / len(self.labels) / VACUUM_VARIANCE


def gaussian_code(variance_snu: float) -> IntervalCode:
    """Gray-coded, equiprobable intervals of a Gaussian modulation, as in Cao et al.

    The modulation variance is in shot-noise units, as in Cao et al. (V_A = 8 SNU). Their
    outer interval [3.25, 7] at 8 SNU is 3.75 / sqrt(8) standard deviations wide.
    """
    sigma = sqrt(variance_snu * VACUUM_VARIANCE)
    gaussian = NormalDist(0.0, sigma)
    bounds = (-inf, *(gaussian.inv_cdf(i / 8) for i in range(1, 8)), inf)
    return IntervalCode(GRAY_LABELS, bounds, tail_width=3.75 / sqrt(8.0) * sigma)


DEFAULT_CODE = IntervalCode(
    labels=("000", "001", "010", "011", "100", "101", "110", "111"),
    bounds=(-inf, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, inf),
    tail_width=1.0,
)

INTERVAL_CODES = {
    "default": DEFAULT_CODE,
    "default_gray": replace(DEFAULT_CODE, labels=GRAY_LABELS),
    "optimized_v4": gaussian_code(4.0),
    "optimized_v8": gaussian_code(8.0),
    "optimized_v12": gaussian_code(12.0),
    # The energy grows linearly with the variance, so this matches the default's energy.
    "optimized_equal_energy": gaussian_code(
        DEFAULT_CODE.energy_snu / gaussian_code(1.0).energy_snu
    ),
}
