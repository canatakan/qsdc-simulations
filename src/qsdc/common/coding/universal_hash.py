from __future__ import annotations

import numpy as np

from .bits import array_to_bits, bits_to_array


class UniversalHash:
    # hash(x) = A x_free + x_fixed (mod 2) with a public random matrix A: the
    # first input bits are free, the last output_bits are fixed by the output.
    # Matrices of this form are a 2-universal family

    def __init__(self, input_bits: int, output_bits: int, seed: int):
        if not 0 < output_bits <= input_bits:
            raise ValueError("the hash must shorten its input to at least one bit")
        self.input_bits = input_bits
        self.output_bits = output_bits
        free_bits = input_bits - output_bits
        rng = np.random.default_rng(seed)
        self._matrix = rng.integers(0, 2, size=(output_bits, free_bits))

    @property
    def free_bits(self) -> int:
        return self.input_bits - self.output_bits

    def hash(self, bits: str) -> str:
        values = bits_to_array(bits)
        free, fixed = values[: self.free_bits], values[self.free_bits :]
        return array_to_bits((self._matrix @ free + fixed) % 2)

    def preimage(self, output: str, randomness: str) -> str:
        # The input whose free part is the given randomness and whose hash is
        # the output. Uniform randomness gives a uniform choice among all inputs
        # with that hash
        free = bits_to_array(randomness)
        fixed = (bits_to_array(output) + self._matrix @ free) % 2
        return randomness + array_to_bits(fixed)

    def rows(self) -> list[list[int]]:
        # Each output bit as the input positions it sums
        result = []
        for i in range(self.output_bits):
            row = [int(j) for j in np.flatnonzero(self._matrix[i])]
            row.append(self.free_bits + i)
            result.append(row)
        return result
