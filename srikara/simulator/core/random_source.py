"""Random sources used by the protocol simulation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from random import Random
from typing import Sequence, TypeVar

T = TypeVar("T")


class RandomSource(ABC):
    """Minimal random-source interface used by protocol decisions."""

    name: str

    @abstractmethod
    def uniform(self, lower: float, upper: float) -> float:
        """Return a random float in [lower, upper]."""

    @abstractmethod
    def choice(self, values: Sequence[T]) -> T:
        """Return one random value from a non-empty sequence."""

    @abstractmethod
    def shuffled(self, values: Sequence[T]) -> list[T]:
        """Return a shuffled copy of a sequence."""


class ClassicalRandomSource(RandomSource):
    """Seeded PRNG used for reproducible simulator runs."""

    name = "classical-seeded"

    def __init__(self, seed: int):
        self._rng = Random(seed)

    def uniform(self, lower: float, upper: float) -> float:
        return self._rng.uniform(lower, upper)

    def choice(self, values: Sequence[T]) -> T:
        return self._rng.choice(values)

    def shuffled(self, values: Sequence[T]) -> list[T]:
        shuffled_values = list(values)
        self._rng.shuffle(shuffled_values)
        return shuffled_values


class IdealQRNG(ClassicalRandomSource):
    """Protocol-level stand-in for a physical QRNG.

    The simulator uses a seeded PRNG underneath so runs are reproducible.
    """

    name = "ideal-qrng"
