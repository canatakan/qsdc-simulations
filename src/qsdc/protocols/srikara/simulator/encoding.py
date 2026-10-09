from __future__ import annotations

from abc import ABC, abstractmethod
from bisect import bisect_right
from dataclasses import dataclass, replace
from math import inf, sqrt
from statistics import NormalDist

from qsdc.common.quadrature import VACUUM_VARIANCE
from qsdc.common.random.base import RandomSource

MESSAGE_DIRECTION = 1 + 1j
BINARY_LABELS = ("000", "001", "010", "011", "100", "101", "110", "111")
GRAY_LABELS = ("000", "001", "011", "010", "110", "100", "101", "111")


@dataclass(frozen=True)
class IntervalCode(ABC):
    labels: tuple[str, ...]
    bounds: tuple[float, ...]

    def interval(self, bits: str) -> tuple[float, float]:
        index = self.labels.index(bits)
        return self.bounds[index], self.bounds[index + 1]

    @abstractmethod
    def sample(self, bits: str, rng: RandomSource) -> float: ...

    def decode(self, value: float) -> str:
        return self.labels[bisect_right(self.bounds, value) - 1]


@dataclass(frozen=True)
class UniformIntervalCode(IntervalCode):
    tail_width: float

    def sample(self, bits: str, rng: RandomSource) -> float:
        lower, upper = self.interval(bits)
        if lower == -inf:
            lower = upper - self.tail_width
        if upper == inf:
            upper = lower + self.tail_width
        return rng.uniform(lower, upper)


@dataclass(frozen=True)
class GaussianIntervalCode(IntervalCode):
    sigma: float

    def sample(self, bits: str, rng: RandomSource) -> float:
        gaussian = NormalDist(0.0, self.sigma)
        lower, upper = self.interval(bits)
        return gaussian.inv_cdf(rng.uniform(gaussian.cdf(lower), gaussian.cdf(upper)))


DEFAULT = UniformIntervalCode(
    BINARY_LABELS, (-inf, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, inf), tail_width=1.0
)
DEFAULT_VARIANCE_SNU = 64 / 3
# Table I of Cao et al. (V_A = 8 SNU), scaled to the default's energy.
CAO_BOUNDS_SNU = (-3.2537, -1.9077, -0.9012, 0.0, 0.9012, 1.9077, 3.2537)
CAO_SCALE = sqrt(DEFAULT_VARIANCE_SNU / 8.0 * VACUUM_VARIANCE)
GAUSSIAN_GRAY = GaussianIntervalCode(
    GRAY_LABELS,
    (-inf, *(bound * CAO_SCALE for bound in CAO_BOUNDS_SNU), inf),
    sigma=sqrt(DEFAULT_VARIANCE_SNU * VACUUM_VARIANCE),
)

INTERVAL_CODES = {
    "default": DEFAULT,
    "gray": replace(DEFAULT, labels=GRAY_LABELS),
    "gaussian_gray": GAUSSIAN_GRAY,
}
