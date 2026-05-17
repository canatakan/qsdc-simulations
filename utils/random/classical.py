"""Classical seeded random source."""

from __future__ import annotations

from random import Random
from typing import Sequence, TypeVar

from .base import RandomSource

T = TypeVar("T")


class ClassicalRandomSource(RandomSource):
    """Seeded classical PRNG for reproducible simulation runs."""

    name = "classical"

    def __init__(self, seed: int):
        self._rng = Random(seed)

    def uniform(self, lower: float, upper: float) -> float:
        return self._rng.uniform(lower, upper)

    def choice(self, values: Sequence[T]) -> T:
        if not values:
            raise ValueError("cannot choose from an empty sequence")
        return self._rng.choice(values)

    def shuffled(self, values: Sequence[T]) -> list[T]:
        shuffled_values = list(values)
        self._rng.shuffle(shuffled_values)
        return shuffled_values

    def _randbelow(self, n: int) -> int:
        if n <= 0:
            raise ValueError("n must be positive")
        return self._rng.randrange(n)
