from __future__ import annotations

from math import exp, sqrt

import numpy as np


class AnalyticBackend:
    def __init__(self, squeeze_r: float):
        self.squeeze_r = squeeze_r
        self._rng = np.random.default_rng()

    def begin_run(self, seed: int) -> None:
        self._rng = np.random.default_rng(seed)

    def measure_check(self) -> tuple[complex, complex]:
        signal, detection = self._pair()
        return self._heterodyne(signal), self._heterodyne(detection)

    def measure_signal(self, displacement: complex) -> complex:
        signal, detection = self._pair()
        info = signal + displacement
        return complex(info.real - detection.real, info.imag + detection.imag) / sqrt(2)

    def _pair(self) -> tuple[complex, complex]:
        r = self.squeeze_r
        x1, p1, x2, p2 = self._rng.standard_normal(4)
        beam1 = complex(exp(-r) * x1, exp(r) * p1)
        beam2 = complex(exp(r) * x2, exp(-r) * p2)
        return (beam1 + beam2) / sqrt(2), (beam2 - beam1) / sqrt(2)

    def _heterodyne(self, mode: complex) -> complex:
        x, p = self._rng.standard_normal(2)
        return complex(mode.real + x, mode.imag - p) / sqrt(2)
