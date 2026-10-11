from __future__ import annotations

from math import exp, sqrt
from typing import Union

import numpy as np

from qsdc.common.noise import Channel, Detector, Memory
from qsdc.protocols.cao.config import NoiseConfig

Link = Union[Channel, Memory]


class AnalyticBackend:
    def __init__(self, squeeze_r: float, noise: NoiseConfig | None = None):
        self.squeeze_r = squeeze_r
        self.noise = noise or NoiseConfig()
        self._rng = np.random.default_rng()

    def begin_run(self, seed: int) -> None:
        self._rng = np.random.default_rng(seed)

    def measure_check(self) -> tuple[complex, complex]:
        noise = self.noise
        signal, detection = self._pair()
        signal = self._transmit(signal, noise.alice_memory)
        detection = self._transmit(detection, noise.channel)
        return (
            self._heterodyne(signal, noise.alice_detector),
            self._heterodyne(detection, noise.bob_detector),
        )

    def measure_signal(self, displacement: complex) -> complex:
        noise = self.noise
        signal, detection = self._pair()
        signal = self._transmit(signal, noise.alice_memory) + displacement
        signal = self._transmit(signal, noise.channel)
        detection = self._transmit(detection, noise.channel)
        detection = self._transmit(detection, noise.bob_memory)
        x = (signal.real - detection.real) / sqrt(2)
        p = (signal.imag + detection.imag) / sqrt(2)
        detector = noise.bob_detector
        return complex(self._detect(x, detector), self._detect(p, detector))

    def _pair(self) -> tuple[complex, complex]:
        r = self.squeeze_r
        vacuum1, vacuum2 = self._vacuum(), self._vacuum()
        beam1 = complex(exp(-r) * vacuum1.real, exp(r) * vacuum1.imag)
        beam2 = complex(exp(r) * vacuum2.real, exp(-r) * vacuum2.imag)
        return (beam1 + beam2) / sqrt(2), (beam2 - beam1) / sqrt(2)

    def _transmit(self, mode: complex, link: Link) -> complex:
        t = link.transmittance
        thermal = sqrt((1 - t) * (2 * link.nbar + 1))
        return sqrt(t) * mode + thermal * self._vacuum()

    def _heterodyne(self, mode: complex, detector: Detector) -> complex:
        vacuum = self._vacuum()
        x = (mode.real + vacuum.real) / sqrt(2)
        p = (mode.imag - vacuum.imag) / sqrt(2)
        return complex(self._detect(x, detector), self._detect(p, detector))

    def _detect(self, value: float, detector: Detector) -> float:
        eta = detector.efficiency
        loss, electronic = self._rng.standard_normal(2)
        return (
            sqrt(eta) * value
            + sqrt(1 - eta) * loss
            + sqrt(detector.electronic_variance) * electronic
        )

    def _vacuum(self) -> complex:
        x, p = self._rng.standard_normal(2)
        return complex(x, p)
