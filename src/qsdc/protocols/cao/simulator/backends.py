from __future__ import annotations

from abc import ABC, abstractmethod
from cmath import phase
from collections.abc import Sequence
from math import acos, cosh, pi, sinh, sqrt
from typing import Union

import numpy as np
from strawberryfields import Engine, Program, ops

from qsdc.common.config.noise import Channel, Detector, Memory
from qsdc.common.quadrature import P, Q, Quadrature

from ..config import NoiseConfig, SimulatorConfig
from ..constants import VACUUM_VARIANCE

Link = Union[Channel, Memory]
# A heterodyne reads x and p of a mode; a homodyne reads one quadrature of it.
HeterodyneReadout = tuple[int, Detector]
HomodyneReadout = tuple[int, Quadrature, Detector]


class Backend(ABC):
    def __init__(self, squeeze_r: float):
        self.squeeze_r = squeeze_r

    def begin_run(self, seed: int) -> None: ...

    @abstractmethod
    def measure_check(self) -> tuple[complex, complex]:
        # Alice's and Bob's heterodyne outcomes x + ip at a check position.
        ...

    @abstractmethod
    def check_sigma(self) -> float:
        # The standard deviation of X_m = (x_A - x_B)/sqrt2 at a check position
        # for an honest pair. Its mean is 0, and P_m = (p_A + p_B)/sqrt2 has the
        # same spread.
        ...

    @abstractmethod
    def measure_signal(self, displacement: complex) -> complex:
        # Bob's joint measurement X_m + i P_m after Alice displaced S1.
        ...


class AnalyticBackend(Backend):
    # The paper's formulas on a noiseless channel. The measurements are the
    # mean values, so nothing is sampled.

    def prepare_pair(self) -> tuple[float, float]:
        # Eqs. 1-4: beam 1 is squeezed in x and beam 2 in p, and the 50:50 beam
        # splitter gives S1 = (beam 1 + beam 2)/sqrt2 and S2 = (beam 2 - beam 1)/sqrt2.
        # Both have the variance cosh 2r, and x_S1, x_S2 the covariance sinh 2r,
        # so Var(x_S1 - x_S2) = 2 e^-2r: the EPR correlation.
        variance = cosh(2 * self.squeeze_r) * VACUUM_VARIANCE
        covariance = sinh(2 * self.squeeze_r) * VACUUM_VARIANCE

        return variance, covariance

    def measure_check(self) -> tuple[complex, complex]:
        return 0j, 0j

    def check_sigma(self) -> float:
        # A heterodyne splits each beam with a vacuum, which halves the variance
        # plus one vacuum and the covariance alone.
        variance, covariance = self.prepare_pair()

        heterodyne = (variance + VACUUM_VARIANCE) / 2
        correlation = covariance / 2

        return sqrt(heterodyne - correlation)

    def measure_signal(self, displacement: complex) -> complex:
        # Eq. 6 combines S_info and S2 on a 50:50 beam splitter, which halves
        # the displacement's power.
        return displacement / sqrt(2)


class StrawberryFieldsBackend(Backend):
    # With hbar = 2, quadratures are in shot-noise units, as in the paper.

    def __init__(self, squeeze_r: float, noise: NoiseConfig | None = None):
        super().__init__(squeeze_r)
        self.noise = noise or NoiseConfig()

    def measure_check(self) -> tuple[complex, complex]:
        noise = self.noise
        alice, bob = self._measure_heterodyne(
            self._check_program(),
            ((1, noise.alice_detector), (0, noise.bob_detector)),
        )

        return alice, bob

    def check_sigma(self) -> float:
        # A heterodyne splits each beam with a vacuum, which halves the variance
        # plus one vacuum and the covariance alone.
        noise = self.noise
        alice_x, bob_x = 1, 0
        covariance = Engine("gaussian").run(self._check_program()).state.cov()

        alice = (covariance[alice_x, alice_x] + VACUUM_VARIANCE) / 2
        bob = (covariance[bob_x, bob_x] + VACUUM_VARIANCE) / 2
        correlation = covariance[alice_x, bob_x] / 2
        electronic = (
            noise.alice_detector.electronic_variance
            + noise.bob_detector.electronic_variance
        ) * VACUUM_VARIANCE

        variance = (alice + bob - 2 * correlation + electronic) / 2
        return sqrt(float(variance))

    def measure_signal(self, displacement: complex) -> complex:
        detector = self.noise.bob_detector
        x, p = self._measure_homodyne(
            self._signal_program(displacement),
            ((1, Q, detector), (0, P, detector)),
        )

        return complex(x, p)

    @abstractmethod
    def _measure_heterodyne(
        self, program: Program, readouts: Sequence[HeterodyneReadout]
    ) -> list[complex]: ...

    @abstractmethod
    def _measure_homodyne(
        self, program: Program, readouts: Sequence[HomodyneReadout]
    ) -> list[float]: ...

    def _check_program(self) -> Program:
        # Modes: 0 = S2 (Bob), 1 = S1 (Alice), 2 and 3 for the losses. The
        # detector loss comes before the heterodyne, which equals the same loss
        # on both of its outputs.
        noise = self.noise

        program = Program(4)
        with program.context as q:
            self._prepare_pair(q)
            self._transmit(q, 1, 2, noise.alice_memory)
            self._transmit(q, 0, 3, noise.channel)
            ops.LossChannel(noise.alice_detector.efficiency) | q[1]
            ops.LossChannel(noise.bob_detector.efficiency) | q[0]

        return program

    def _signal_program(self, displacement: complex) -> Program:
        # Modes: 0 = S2, 1 = S1, 2 to 5 for the losses. Step 6's heterodyne has
        # S2 in place of the vacuum, so it is built here: a beam splitter, then
        # Bob reads x on mode 1 and p on mode 0.
        noise = self.noise
        signal, detection = 1, 0

        program = Program(6)
        with program.context as q:
            self._prepare_pair(q)
            self._transmit(q, signal, 2, noise.alice_memory)

            # A displacement d moves the quadratures by d when alpha = d / 2.
            ops.Dgate(abs(displacement) / 2, phase(displacement)) | q[signal]
            self._transmit(q, signal, 3, noise.channel)
            self._transmit(q, detection, 4, noise.channel)
            self._transmit(q, detection, 5, noise.bob_memory)

            # Eq. 6: X of (S_info - S2)/sqrt2 and P of (S_info + S2)/sqrt2.
            ops.BSgate(pi / 4, 0.0) | (q[signal], q[detection])
            ops.LossChannel(noise.bob_detector.efficiency) | q[signal]
            ops.LossChannel(noise.bob_detector.efficiency) | q[detection]

        return program

    def _prepare_pair(self, q: object) -> None:
        # Eqs. 1-4: an x-squeezed and a p-squeezed vacuum on a 50:50 beam
        # splitter. Mode 1 becomes S1, and mode 0 rotated by pi becomes S2.
        r = self.squeeze_r

        ops.Sgate(r, 0.0) | q[0]
        ops.Sgate(r, pi) | q[1]
        ops.BSgate(pi / 4, 0.0) | (q[0], q[1])
        ops.Rgate(pi) | q[0]

    @staticmethod
    def _transmit(q: object, mode: int, spare: int, link: Link) -> None:
        # A thermal loss channel: a beam splitter with transmittance T that mixes
        # the beam with a thermal state. Strawberry Fields 0.23's
        # ThermalLossChannel adds its thermal photons to every mode of the
        # circuit, so it is built here.
        ops.Thermal(link.nbar) | q[spare]
        ops.BSgate(acos(sqrt(link.transmittance)), 0.0) | (q[mode], q[spare])


class SFAnalyticBackend(StrawberryFieldsBackend):
    def _measure_heterodyne(
        self, program: Program, readouts: Sequence[HeterodyneReadout]
    ) -> list[complex]:
        state = Engine("gaussian").run(program).state

        values = []
        for mode, _ in readouts:
            x = state.quad_expectation(mode, Q.angle)[0]
            p = state.quad_expectation(mode, P.angle)[0]
            # The heterodyne's beam splitter halves the power.
            values.append(complex(x, p) / sqrt(2))

        return values

    def _measure_homodyne(
        self, program: Program, readouts: Sequence[HomodyneReadout]
    ) -> list[float]:
        state = Engine("gaussian").run(program).state

        return [
            float(state.quad_expectation(mode, axis.angle)[0])
            for mode, axis, _ in readouts
        ]


class SFSampledBackend(StrawberryFieldsBackend):
    def begin_run(self, seed: int) -> None:
        np.random.seed(seed)

    def _measure_heterodyne(
        self, program: Program, readouts: Sequence[HeterodyneReadout]
    ) -> list[complex]:
        with program.context as q:
            for mode, _ in readouts:
                ops.MeasureHeterodyne() | q[mode]

        samples = Engine("gaussian").run(program).samples[0]

        values = []
        for mode, detector in readouts:
            # Strawberry Fields returns alpha with x = 2 Re(alpha), the
            # quadrature plus a vacuum. The heterodyne's beam splitter halves
            # its power, which gives sqrt2 alpha.
            value = sqrt(2) * complex(samples[mode])
            value += complex(*self._electronic_noise(detector, 2))
            values.append(value)

        return values

    def _measure_homodyne(
        self, program: Program, readouts: Sequence[HomodyneReadout]
    ) -> list[float]:
        with program.context as q:
            for mode, axis, _ in readouts:
                ops.MeasureHomodyne(axis.angle) | q[mode]

        samples = Engine("gaussian").run(program).samples[0]

        values = []
        for mode, _, detector in readouts:
            (noise,) = self._electronic_noise(detector, 1)
            values.append(float(samples[mode]) + noise)

        return values

    @staticmethod
    def _electronic_noise(detector: Detector, count: int) -> np.ndarray:
        # Drawn even without electronic noise, so every case uses the same
        # random stream.
        sigma = sqrt(detector.electronic_variance * VACUUM_VARIANCE)
        return np.random.normal(0.0, sigma, count)


def make_backend(config: SimulatorConfig) -> Backend:
    if config.backend == "analytic":
        return AnalyticBackend(config.squeeze_r)

    if config.backend == "sf":
        return SFAnalyticBackend(config.squeeze_r, config.noise)

    return SFSampledBackend(config.squeeze_r, config.noise)
