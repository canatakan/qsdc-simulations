from __future__ import annotations

from collections import deque

import numpy as np
import strawberryfields as sf
from strawberryfields import ops

from qsdc.common.random.base import RandomSource


class SFBeamSplitterQRNG(RandomSource):
    name = "sf-bs-qrng"

    def __init__(self, seed: int | None = None, batch_size: int = 1024):
        self.seed = seed
        self.batch_size = batch_size
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

        numpy_state = np.random.get_state()
        if self.seed is not None:
            np.random.seed(
                np.random.SeedSequence((self.seed, self._refills)).generate_state(1)[0]
            )
            self._refills += 1
        try:
            for _ in range(self.batch_size):
                photon_counts = (
                    sf.Engine("fock", backend_options={"cutoff_dim": 2})
                    .run(program)
                    .samples[0]
                )
                self._bits.append(int(photon_counts[1]))
        finally:
            np.random.set_state(numpy_state)
