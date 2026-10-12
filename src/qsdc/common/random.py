from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Sequence
from math import cos, log, pi, sqrt
from random import Random
from typing import TypeVar

import numpy as np
import strawberryfields as sf
from strawberryfields import ops

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


class ClassicalRandomSource(RandomSource):
    name = "classical"

    def __init__(self, seed: int):
        self._rng = Random(seed)

    def uniform(self, lower: float, upper: float) -> float:
        return self._rng.uniform(lower, upper)

    def randbelow(self, n: int) -> int:
        return self._rng.randrange(n)


class SFBeamSplitterQRNG(RandomSource):
    name = "sf-bs-qrng"
    BATCH = 1024

    def __init__(self, seed: int | None = None):
        self.seed = seed
        self._bits: deque[int] = deque()
        self._refills = 0

    def uniform(self, lower: float, upper: float) -> float:
        return lower + (upper - lower) * self._integer(53) / (1 << 53)

    def randbelow(self, n: int) -> int:
        while True:
            candidate = self._integer(n.bit_length())
            if candidate < n:
                return candidate

    def raw_bit(self) -> int:
        if not self._bits:
            self._refill()

        return self._bits.popleft()

    def _integer(self, bits: int) -> int:
        value = 0
        for _ in range(bits):
            value = (value << 1) | self.raw_bit()

        return value

    def _refill(self) -> None:
        program = sf.Program(2)
        with program.context as q:
            ops.Fock(1) | q[0]
            ops.BSgate(np.pi / 4, 0.0) | (q[0], q[1])
            ops.MeasureFock() | q

        # Seed numpy for the Fock samples, and restore its state afterwards.
        numpy_state = np.random.get_state()
        if self.seed is not None:
            np.random.seed(
                np.random.SeedSequence((self.seed, self._refills)).generate_state(1)[0]
            )
            self._refills += 1

        try:
            for _ in range(self.BATCH):
                photon_counts = (
                    sf.Engine("fock", backend_options={"cutoff_dim": 2})
                    .run(program)
                    .samples[0]
                )
                self._bits.append(int(photon_counts[1]))
        finally:
            np.random.set_state(numpy_state)


def make_random_source(name: str, seed: int) -> RandomSource:
    return {"classical": ClassicalRandomSource, "sf-bs-qrng": SFBeamSplitterQRNG}[name](
        seed
    )


def derive_seed(*parts: object) -> int:
    digest = hashlib.sha256()
    for part in parts:
        encoded = str(part).encode()
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)

    return int.from_bytes(digest.digest()[:4], "big")


def weighted_random_bits(count: int, one_probability: float, rng: RandomSource) -> str:
    return "".join(
        "1" if rng.uniform(0.0, 1.0) < one_probability else "0" for _ in range(count)
    )
