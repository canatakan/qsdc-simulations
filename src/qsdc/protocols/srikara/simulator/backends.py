from __future__ import annotations

from abc import ABC, abstractmethod
from cmath import exp, polar
from dataclasses import dataclass
from math import cosh, sinh, sqrt

import numpy as np
from strawberryfields import Engine, Program, hbar, ops

from qsdc.common.config.noise import Detector
from qsdc.common.quadrature import Quadrature

from ..config import NoiseConfig, SimulatorConfig
from ..constants import MESSAGE_DIRECTION, VACUUM_VARIANCE

SF_SCALE = sqrt(2.0 * hbar)


@dataclass(frozen=True)
class PreparedState:
    index: int
    alpha: complex
    squeeze_r: float
    theta: float


@dataclass(frozen=True)
class Expectation:
    mean: float
    sigma: float


class Backend(ABC):
    def prepare_run(self, seed: int) -> None: ...

    @abstractmethod
    def measure_control(self, state: PreparedState, axis: Quadrature) -> float: ...

    @abstractmethod
    def measure_returned(
        self, state: PreparedState, axis: Quadrature, beta: complex = 0j
    ) -> float: ...

    @abstractmethod
    def expect_control(self, state: PreparedState, axis: Quadrature) -> Expectation: ...

    @abstractmethod
    def expect_returned(
        self, state: PreparedState, axis: Quadrature
    ) -> Expectation: ...

    @abstractmethod
    def message_response(self, state: PreparedState, axis: Quadrature) -> float: ...


class AnalyticBackend(Backend):
    @staticmethod
    def squeezed_displacement(
        alpha: complex, squeeze_r: float, theta: float
    ) -> complex:
        """beta = alpha cosh r + e^{i theta} alpha* sinh r"""
        conjugate_part = exp(1j * theta) * alpha.conjugate() * sinh(squeeze_r)
        return alpha * cosh(squeeze_r) + conjugate_part

    @staticmethod
    def unsqueezed_displacement(
        beta: complex, squeeze_r: float, theta: float
    ) -> complex:
        """Delta = beta cosh r - e^{i theta} beta* sinh r"""
        conjugate_part = exp(1j * theta) * beta.conjugate() * sinh(squeeze_r)
        return beta * cosh(squeeze_r) - conjugate_part

    def measure_control(self, state: PreparedState, axis: Quadrature) -> float:
        return axis.component(state.alpha)

    def measure_returned(
        self, state: PreparedState, axis: Quadrature, beta: complex = 0j
    ) -> float:
        delta = self.unsqueezed_displacement(beta, state.squeeze_r, state.theta)
        return axis.component(state.alpha + delta)

    def expect_control(self, state: PreparedState, axis: Quadrature) -> Expectation:
        return Expectation(axis.component(state.alpha), 0.0)

    def expect_returned(self, state: PreparedState, axis: Quadrature) -> Expectation:
        return self.expect_control(state, axis)

    def message_response(self, state: PreparedState, axis: Quadrature) -> float:
        delta = self.unsqueezed_displacement(
            MESSAGE_DIRECTION, state.squeeze_r, state.theta
        )
        return axis.component(delta)


class StrawberryFieldsBackend(Backend):
    def __init__(self, noise: NoiseConfig):
        self.noise = noise
        self._responses: dict[tuple[float, float], complex] = {}

    def measure_control(self, state: PreparedState, axis: Quadrature) -> float:
        return self._measure(
            self._control_program(state), axis, self.noise.alice_detector
        )

    def measure_returned(
        self, state: PreparedState, axis: Quadrature, beta: complex = 0j
    ) -> float:
        return self._measure(
            self._returned_program(state, beta), axis, self.noise.bob_detector
        )

    def expect_control(self, state: PreparedState, axis: Quadrature) -> Expectation:
        return self._expect(
            self._control_program(state), axis, self.noise.alice_detector
        )

    def expect_returned(self, state: PreparedState, axis: Quadrature) -> Expectation:
        return self._expect(
            self._returned_program(state, 0j), axis, self.noise.bob_detector
        )

    def message_response(self, state: PreparedState, axis: Quadrature) -> float:
        # The response depends only on r and theta, so it is cached per pair.
        key = (state.squeeze_r, state.theta)
        if key not in self._responses:
            unit = PreparedState(state.index, 0j, state.squeeze_r, state.theta)
            program = self._returned_program(unit, MESSAGE_DIRECTION)
            q, p = Engine("gaussian").run(program).state.means() / SF_SCALE
            self._responses[key] = complex(q, p)

        return axis.component(self._responses[key])

    @abstractmethod
    def _measure(
        self, program: Program, axis: Quadrature, detector: Detector
    ) -> float: ...

    @staticmethod
    def _expect(program: Program, axis: Quadrature, detector: Detector) -> Expectation:
        mean, variance = (
            Engine("gaussian").run(program).state.quad_expectation(0, axis.angle)
        )

        variance = (
            variance / SF_SCALE**2 + detector.electronic_variance * VACUUM_VARIANCE
        )

        return Expectation(float(mean) / SF_SCALE, sqrt(variance))

    def _control_program(self, state: PreparedState) -> Program:
        program = Program(1)
        with program.context as q:
            self._send(state, q[0])
            ops.Sgate(state.squeeze_r, state.theta) | q[0]
            ops.LossChannel(self.noise.alice_detector.efficiency) | q[0]

        return program

    def _returned_program(self, state: PreparedState, beta: complex) -> Program:
        memory, backward = self.noise.memory, self.noise.backward

        program = Program(1)
        with program.context as q:
            self._send(state, q[0])
            ops.ThermalLossChannel(memory.transmittance, memory.nbar) | q[0]
            ops.Dgate(*polar(beta)) | q[0]
            ops.ThermalLossChannel(backward.transmittance, backward.nbar) | q[0]
            ops.Sgate(state.squeeze_r, state.theta) | q[0]
            ops.LossChannel(self.noise.bob_detector.efficiency) | q[0]

        return program

    def _send(self, state: PreparedState, mode: object) -> None:
        forward = self.noise.forward

        ops.Dgate(*polar(state.alpha)) | mode
        # Strawberry Fields' squeezing sign convention is opposite to the paper's.
        ops.Sgate(-state.squeeze_r, state.theta) | mode
        ops.ThermalLossChannel(forward.transmittance, forward.nbar) | mode


class SFAnalyticBackend(StrawberryFieldsBackend):
    # Reads out the exact mean of each circuit

    def _measure(self, program: Program, axis: Quadrature, detector: Detector) -> float:
        return self._expect(program, axis, detector).mean


class SFSampledBackend(StrawberryFieldsBackend):
    # Reads out a homodyne sample of each circuit

    def prepare_run(self, seed: int) -> None:
        np.random.seed(seed)

    def _measure(self, program: Program, axis: Quadrature, detector: Detector) -> float:
        with program.context as q:
            ops.MeasureHomodyne(axis.angle) | q[0]

        value = float(Engine("gaussian").run(program).samples[0, 0]) / SF_SCALE
        # Drawn even without electronic noise, so every case uses the same random stream.
        value += np.random.normal(
            0.0, sqrt(detector.electronic_variance * VACUUM_VARIANCE)
        )

        return value


def make_backend(config: SimulatorConfig) -> Backend:
    if config.backend == "analytic":
        return AnalyticBackend()

    if config.backend == "sf":
        return SFAnalyticBackend(config.noise)

    return SFSampledBackend(config.noise)
