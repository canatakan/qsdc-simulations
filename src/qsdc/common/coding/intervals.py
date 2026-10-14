from __future__ import annotations

from abc import ABC, abstractmethod
from bisect import bisect_right
from dataclasses import dataclass
from math import inf, sqrt
from statistics import NormalDist

from ..random import RandomSource


def binary_labels(width: int) -> tuple[str, ...]:
    return tuple(f"{index:0{width}b}" for index in range(2**width))


BINARY_LABELS = binary_labels(3)
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

        # The open outer intervals are sampled over one tail width.
        if lower == -inf:
            lower = upper - self.tail_width
        if upper == inf:
            upper = lower + self.tail_width

        return rng.uniform(lower, upper)


@dataclass(frozen=True)
class GaussianIntervalCode(IntervalCode):
    sigma: float

    @classmethod
    def equiprobable(
        cls, labels: tuple[str, ...], sigma: float
    ) -> GaussianIntervalCode:
        gaussian = NormalDist(0.0, sigma)
        count = len(labels)
        inner = tuple(gaussian.inv_cdf(k / count) for k in range(1, count))

        return cls(labels, (-inf, *inner, inf), sigma)

    def sample(self, bits: str, rng: RandomSource) -> float:
        gaussian = NormalDist(0.0, self.sigma)
        lower, upper = self.interval(bits)

        return gaussian.inv_cdf(rng.uniform(gaussian.cdf(lower), gaussian.cdf(upper)))

    def probabilities(self, value: float, noise_variance: float) -> dict[str, float]:
        # The value is Gaussian with variance sigma^2, read with Gaussian noise.
        # Given the reading, it is Gaussian around the reading pulled towards 0.
        prior_variance = self.sigma**2
        shrink = prior_variance / (prior_variance + noise_variance)
        posterior = NormalDist(value * shrink, sqrt(shrink * noise_variance))

        probabilities = {}
        for label in self.labels:
            lower, upper = self.interval(label)
            probabilities[label] = posterior.cdf(upper) - posterior.cdf(lower)

        return probabilities
