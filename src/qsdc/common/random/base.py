from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


class RandomSource(ABC):
    """Randomness used by the protocols; choice and shuffle match Python's `random` for equal draws."""

    name: str

    @abstractmethod
    def uniform(self, lower: float, upper: float) -> float: ...

    @abstractmethod
    def randbelow(self, n: int) -> int: ...

    def choice(self, values: Sequence[T]) -> T:
        return values[self.randbelow(len(values))]

    def shuffled(self, values: Sequence[T]) -> list[T]:
        result = list(values)
        for i in reversed(range(1, len(result))):
            j = self.randbelow(i + 1)
            result[i], result[j] = result[j], result[i]
        return result
