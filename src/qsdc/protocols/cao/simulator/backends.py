from __future__ import annotations

from math import cosh, exp, sinh, sqrt
from typing import Union

import numpy as np

from qsdc.common.config.noise import Channel, Detector, Memory
from qsdc.protocols.cao.config import NoiseConfig
from qsdc.protocols.cao.constants import VACUUM_VARIANCE

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

    def check_variance(self) -> float:
        # Variance of X_m (and of P_m) at a check position for an honest pair:
        # both beams are attenuated, and each heterodyne adds vacuum and detector noise.
        noise = self.noise
        alice_link, bob_link = noise.alice_memory, noise.channel
        alice_detector, bob_detector = noise.alice_detector, noise.bob_detector
        beam_variance = cosh(2 * self.squeeze_r) * VACUUM_VARIANCE
        beam_covariance = sinh(2 * self.squeeze_r) * VACUUM_VARIANCE

        alice = _heterodyne_variance(
            _transmitted_variance(beam_variance, alice_link), alice_detector
        )
        bob = _heterodyne_variance(
            _transmitted_variance(beam_variance, bob_link), bob_detector
        )
        covariance = (
            sqrt(alice_detector.efficiency * bob_detector.efficiency)
            * sqrt(alice_link.transmittance * bob_link.transmittance)
            * beam_covariance
            / 2
        )
        return (alice + bob - 2 * covariance) / 2

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
        loss, electronic = self._rng.normal(0.0, sqrt(VACUUM_VARIANCE), 2)
        return (
            sqrt(eta) * value
            + sqrt(1 - eta) * loss
            + sqrt(detector.electronic_variance) * electronic
        )

    def _vacuum(self) -> complex:
        x, p = self._rng.normal(0.0, sqrt(VACUUM_VARIANCE), 2)
        return complex(x, p)


def _transmitted_variance(variance: float, link: Link) -> float:
    t = link.transmittance
    return t * variance + (1 - t) * (2 * link.nbar + 1) * VACUUM_VARIANCE


def _heterodyne_variance(variance: float, detector: Detector) -> float:
    eta = detector.efficiency
    split = (variance + VACUUM_VARIANCE) / 2
    return (
        eta * split
        + (1 - eta) * VACUUM_VARIANCE
        + detector.electronic_variance * VACUUM_VARIANCE
    )
