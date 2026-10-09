from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from math import cos, log, pi, sqrt
from typing import TypeVar

T = TypeVar("T")


class RandomSource(ABC):
    name: str

    @abstractmethod
    def uniform(self, lower: float, upper: float) -> float: ...

    @abstractmethod
    def randbelow(self, n: int) -> int: ...

    def gauss(self, sigma: float) -> float:
        radius = sqrt(-2.0 * log(1.0 - self.uniform(0.0, 1.0)))
        return sigma * radius * cos(2.0 * pi * self.uniform(0.0, 1.0))

    def choice(self, values: Sequence[T]) -> T:
        return values[self.randbelow(len(values))]

    def shuffled(self, values: Sequence[T]) -> list[T]:
        result = list(values)
        for i in reversed(range(1, len(result))):
            j = self.randbelow(i + 1)
            result[i], result[j] = result[j], result[i]
        return result
