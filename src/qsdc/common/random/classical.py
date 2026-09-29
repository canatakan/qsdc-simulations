from __future__ import annotations

from random import Random

from qsdc.common.random.base import RandomSource


class ClassicalRandomSource(RandomSource):
    name = "classical"

    def __init__(self, seed: int):
        self._rng = Random(seed)

    def uniform(self, lower: float, upper: float) -> float:
        return self._rng.uniform(lower, upper)

    def randbelow(self, n: int) -> int:
        return self._rng.randrange(n)
