"""Shared random-source base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence, TypeVar

T = TypeVar("T")


class RandomSource(ABC):
    """Minimal random-source interface used by simulator protocols."""

    name: str

    @abstractmethod
    def uniform(self, lower: float, upper: float) -> float:
        """Return a random float."""

    @abstractmethod
    def choice(self, values: Sequence[T]) -> T:
        """Return one random value from a non-empty sequence."""

    def shuffled(self, values: Sequence[T]) -> list[T]:
        # Make a copy of the input sequence so the original values are not modified.
        shuffled_values = list(values)

        # Shuffle the list using the Fisher–Yates shuffle algorithm.
        # Walk backward through the list, placing one randomly selected item
        # into its final shuffled position on each iteration.
        for index in range(len(shuffled_values) - 1, 0, -1):
            # Pick a random index from the unshuffled portion of the list:
            # any position from 0 through the current index, inclusive.
            swap_index = self._randbelow(index + 1)

            # Swap the current item with the randomly selected item.
            shuffled_values[index], shuffled_values[swap_index] = (
                shuffled_values[swap_index],
                shuffled_values[index],
            )

        # Return the shuffled copy.
        return shuffled_values

    @abstractmethod
    def _randbelow(self, n: int) -> int:
        """Return an unbiased integer in range(n)."""
