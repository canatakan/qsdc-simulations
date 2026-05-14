"""Random sources used by the protocol simulation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from random import Random
from typing import Sequence, TypeVar

import numpy as np
import strawberryfields as sf
from strawberryfields import ops

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

    name = "classical"

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


class SFBeamSplitterQRNG(RandomSource):
    """Simulated beam-splitter QRNG using Strawberry Fields.

    A single photon enters one port of a 50:50 beam splitter while vacuum enters
    the other. Fock measurement of the output mode containing the photon gives a
    raw bit.
    """

    name = "sf-bs-qrng"

    def __init__(
        self,
        *,
        seed: int | None = None,
        batch_size: int = 1024,
        cutoff_dim: int = 2,
    ):
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if cutoff_dim < 2:
            raise ValueError("cutoff_dim must be at least 2")

        self.batch_size = batch_size
        self.cutoff_dim = cutoff_dim
        self._bits: deque[int] = deque()
        self._seed = seed
        self._refill_count = 0

    def uniform(self, lower: float, upper: float) -> float:
        if upper < lower:
            raise ValueError("upper must be >= lower")
        return lower + (upper - lower) * self.random_unit_float()

    def choice(self, values: Sequence[T]) -> T:
        if not values:
            raise ValueError("cannot choose from an empty sequence")
        return values[self._randbelow(len(values))]

    def shuffled(self, values: Sequence[T]) -> list[T]:
        shuffled_values = list(values)
        for index in range(len(shuffled_values) - 1, 0, -1):
            swap_index = self._randbelow(index + 1)
            shuffled_values[index], shuffled_values[swap_index] = (
                shuffled_values[swap_index],
                shuffled_values[index],
            )
        return shuffled_values

    def raw_bit(self) -> int:
        if not self._bits:
            self._refill_bits()
        return self._bits.popleft()

    def random_bits_as_int(self, n_bits: int) -> int:
        if n_bits <= 0:
            raise ValueError("n_bits must be positive")

        value = 0
        for _ in range(n_bits):
            value = (value << 1) | self.raw_bit()
        return value

    def random_unit_float(self) -> float:
        # Generate a 53-bit random integer and scale it into the interval [0, 1).
        return self.random_bits_as_int(53) / (1 << 53)

    def _program(self) -> sf.Program:
        prog = sf.Program(2)
        with prog.context as q:
            ops.Fock(1) | q[0]
            ops.Vacuum() | q[1]
            ops.BSgate(np.pi / 4, 0.0) | (q[0], q[1])
            ops.MeasureFock() | q
        return prog

    def _refill_bits(self) -> None:
        numpy_state = np.random.get_state()
        if self._seed is not None:
            seed = np.random.SeedSequence((self._seed, self._refill_count))
            np.random.seed(seed.generate_state(1)[0])
            self._refill_count += 1

        try:
            samples = []
            for _ in range(self.batch_size):
                engine = sf.Engine(
                    "fock",
                    backend_options={"cutoff_dim": self.cutoff_dim},
                )
                samples.extend(engine.run(self._program()).samples)
        finally:
            np.random.set_state(numpy_state)

        for sample in samples:
            measurement = (int(sample[0]), int(sample[1]))
            if measurement == (1, 0):
                self._bits.append(0)
            elif measurement == (0, 1):
                self._bits.append(1)
            else:
                raise RuntimeError(
                    f"unexpected beam-splitter measurement result: {sample}"
                )

    def _randbelow(self, n: int) -> int:
        if n <= 0:
            raise ValueError("n must be positive")

        n_bits = n.bit_length()
        while True:
            candidate = self.random_bits_as_int(n_bits)
            if candidate < n:
                return candidate
