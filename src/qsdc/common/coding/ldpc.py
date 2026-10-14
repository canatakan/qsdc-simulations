from __future__ import annotations

from collections.abc import Sequence
from math import log

import numpy as np

from .bits import array_to_bits, bits_to_array

MAX_CONFIDENCE = 30.0


class LdpcCode:
    @staticmethod
    def log_ratio(zero: float, one: float) -> float:
        # The decoder's confidence in a bit from its probabilities of 0 and 1.
        if zero <= 0 and one <= 0:
            return 0.0

        if one <= 0:
            return MAX_CONFIDENCE

        if zero <= 0:
            return -MAX_CONFIDENCE

        return log(zero / one)

    def __init__(self, length: int, rows: Sequence[Sequence[int]]):
        self.length = length
        self.rows = tuple(tuple(sorted(set(row))) for row in rows)

        # One entry per edge between a check (row) and a bit, ordered by check.
        edge_checks, edge_bits = [], []
        for check, row in enumerate(self.rows):
            for bit in row:
                edge_checks.append(check)
                edge_bits.append(bit)
        self._edge_check = np.array(edge_checks, dtype=np.int64)
        self._edge_bit = np.array(edge_bits, dtype=np.int64)
        row_lengths = [len(row) for row in self.rows]
        self._row_start = np.cumsum([0, *row_lengths[:-1]])

    @classmethod
    def regular(
        cls, length: int, checks: int, column_weight: int, seed: int
    ) -> LdpcCode:
        # Every bit appears in column_weight checks: shuffle all its appearances
        # and deal them out to the checks in turn. A bit dealt twice to the same
        # check cancels out, as in a sum modulo 2.
        rng = np.random.default_rng(seed)
        appearances = rng.permutation(np.repeat(np.arange(length), column_weight))
        rows: list[set[int]] = [set() for _ in range(checks)]
        for turn, bit in enumerate(appearances):
            row = rows[turn % checks]
            if bit in row:
                row.remove(bit)
            else:
                row.add(int(bit))
        return cls(length, [row for row in rows if row])

    def extended(self, rows: Sequence[Sequence[int]]) -> LdpcCode:
        return LdpcCode(self.length, [*self.rows, *rows])

    @property
    def checks(self) -> int:
        return len(self.rows)

    def syndrome(self, bits: str) -> str:
        return array_to_bits(self._syndrome(bits_to_array(bits)))

    def decode(
        self,
        confidences: Sequence[float],
        syndrome: str,
        max_iterations: int = 100,
        scale: float = 0.75,
    ) -> str | None:
        prior = np.clip(
            np.array(confidences, dtype=float), -MAX_CONFIDENCE, MAX_CONFIDENCE
        )
        target = bits_to_array(syndrome)

        bit_to_check = prior[self._edge_bit]
        for _ in range(max_iterations):
            check_to_bit = scale * self._check_messages(bit_to_check, target)
            belief = prior + np.bincount(
                self._edge_bit, weights=check_to_bit, minlength=self.length
            )
            bits = (belief < 0).astype(np.uint8)
            if np.array_equal(self._syndrome(bits), target):
                return array_to_bits(bits)
            bit_to_check = belief[self._edge_bit] - check_to_bit
        return None

    def _check_messages(
        self, bit_to_check: np.ndarray, target: np.ndarray
    ) -> np.ndarray:
        # Min-sum: a check tells each of its bits the value that would satisfy it,
        # judged from its other bits, with the confidence of the least certain one.
        strength = self._smallest_of_others(np.abs(bit_to_check))
        ones = (bit_to_check < 0).astype(np.int64)
        ones_among_others = self._per_check(np.add, ones) - ones
        says_one = (ones_among_others + target[self._edge_check]) % 2 == 1
        return np.where(says_one, -strength, strength)

    def _smallest_of_others(self, strength: np.ndarray) -> np.ndarray:
        smallest = self._per_check(np.minimum, strength)
        is_smallest = strength == smallest
        only_smallest = is_smallest & (self._per_check(np.add, is_smallest) == 1)
        second = self._per_check(np.minimum, np.where(is_smallest, np.inf, strength))
        others = np.where(only_smallest, second, smallest)
        return np.minimum(others, MAX_CONFIDENCE)

    def _per_check(self, operation: np.ufunc, values: np.ndarray) -> np.ndarray:
        # Combine the values on each check's edges, then hand the result back to
        # every edge of that check.
        per_check = operation.reduceat(values, self._row_start)
        return per_check[self._edge_check]

    def _syndrome(self, bits: np.ndarray) -> np.ndarray:
        ones = np.bincount(
            self._edge_check, weights=bits[self._edge_bit], minlength=self.checks
        )
        return (ones % 2).astype(np.uint8)
