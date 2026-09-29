"""Homodyne measurements from the paper's closed-form algebra or from Strawberry Fields circuits."""

from __future__ import annotations

from abc import ABC, abstractmethod
from cmath import exp, polar
from dataclasses import dataclass
from math import cosh, sinh, sqrt

import numpy as np
from strawberryfields import Engine, Program, hbar, ops

from qsdc.common.quadrature import QuadratureAxis
from qsdc.protocols.srikara.config import Detector, NoiseConfig, SimulatorConfig
from qsdc.protocols.srikara.simulator.encoding import MESSAGE_DIRECTION

# Quadratures are reported in units where the vacuum variance is 1/4.
SF_SCALE = sqrt(2.0 * hbar)
VACUUM_VARIANCE = 0.25


@dataclass(frozen=True)
class PreparedState:
    """Bob's state S(s)D(alpha)|0> with s = r exp(i theta)."""

    index: int
    alpha: complex
    squeeze_r: float
    theta: float


@dataclass(frozen=True)
class Expectation:
    mean: float
    sigma: float


class Backend(ABC):
    """Alice measures control modes; Bob measures the modes that come back from Alice."""

    def begin_run(self, seed: int) -> None:
        """Reseed measurement randomness for one protocol run."""

    @abstractmethod
    def measure_control(self, state: PreparedState, axis: QuadratureAxis) -> float: ...

    @abstractmethod
    def measure_returned(
        self, state: PreparedState, axis: QuadratureAxis, beta: complex = 0j
    ) -> float: ...

    @abstractmethod
    def expect_control(
        self, state: PreparedState, axis: QuadratureAxis
    ) -> Expectation: ...

    @abstractmethod
    def expect_returned(
        self, state: PreparedState, axis: QuadratureAxis
    ) -> Expectation:
        """Expected measurement of a returned mode without a message, i.e. a decoy."""

    @abstractmethod
    def message_response(self, state: PreparedState, axis: QuadratureAxis) -> float:
        """Shift of Bob's measurement per unit message value m_A."""


class AnalyticBackend(Backend):
    """The paper's noiseless algebra: after S(-s), a mode Alice displaced is D(alpha + Delta)|0>."""

    @staticmethod
    def squeezed_displacement(
        alpha: complex, squeeze_r: float, theta: float
    ) -> complex:
        """beta in S(s)D(alpha) = D(beta)S(s): alpha cosh r + exp(i theta) alpha* sinh r."""
        return alpha * cosh(squeeze_r) + exp(1j * theta) * alpha.conjugate() * sinh(
            squeeze_r
        )

    @staticmethod
    def unsqueezed_displacement(
        beta: complex, squeeze_r: float, theta: float
    ) -> complex:
        """Delta, the displacement D(beta) seen after S(-s): beta cosh r - exp(i theta) beta* sinh r."""
        return beta * cosh(squeeze_r) - exp(1j * theta) * beta.conjugate() * sinh(
            squeeze_r
        )

    def measure_control(self, state: PreparedState, axis: QuadratureAxis) -> float:
        return axis.component(state.alpha)

    def measure_returned(
        self, state: PreparedState, axis: QuadratureAxis, beta: complex = 0j
    ) -> float:
        delta = self.unsqueezed_displacement(beta, state.squeeze_r, state.theta)
        return axis.component(state.alpha + delta)

    def expect_control(self, state: PreparedState, axis: QuadratureAxis) -> Expectation:
        return Expectation(axis.component(state.alpha), 0.0)

    def expect_returned(
        self, state: PreparedState, axis: QuadratureAxis
    ) -> Expectation:
        return self.expect_control(state, axis)

    def message_response(self, state: PreparedState, axis: QuadratureAxis) -> float:
        delta = self.unsqueezed_displacement(
            MESSAGE_DIRECTION, state.squeeze_r, state.theta
        )
        return axis.component(delta)


class StrawberryFieldsBackend(Backend):
    """Gaussian circuits with the configured noise, read out as exact means or sampled homodyne values."""

    def __init__(self, noise: NoiseConfig, sampled: bool):
        self.noise = noise
        self.sampled = sampled
        # The unit response depends only on the squeezing, so it is simulated once per s.
        self._responses: dict[tuple[float, float], complex] = {}

    def begin_run(self, seed: int) -> None:
        if self.sampled:
            np.random.seed(seed)

    def measure_control(self, state: PreparedState, axis: QuadratureAxis) -> float:
        return self._measure(
            self._control_program(state), axis, self.noise.alice_detector
        )

    def measure_returned(
        self, state: PreparedState, axis: QuadratureAxis, beta: complex = 0j
    ) -> float:
        return self._measure(
            self._returned_program(state, beta), axis, self.noise.bob_detector
        )

    def expect_control(self, state: PreparedState, axis: QuadratureAxis) -> Expectation:
        return self._expect(
            self._control_program(state), axis, self.noise.alice_detector
        )

    def expect_returned(
        self, state: PreparedState, axis: QuadratureAxis
    ) -> Expectation:
        return self._expect(
            self._returned_program(state, 0j), axis, self.noise.bob_detector
        )

    def message_response(self, state: PreparedState, axis: QuadratureAxis) -> float:
        """Mean Bob measures when Alice displaces an alpha = 0 state by 1 + i."""
        key = (state.squeeze_r, state.theta)
        if key not in self._responses:
            unit = PreparedState(state.index, 0j, state.squeeze_r, state.theta)
            program = self._returned_program(unit, MESSAGE_DIRECTION)
            q, p = Engine("gaussian").run(program).state.means() / SF_SCALE
            self._responses[key] = complex(q, p)
        return axis.component(self._responses[key])

    def _measure(
        self, program: Program, axis: QuadratureAxis, detector: Detector
    ) -> float:
        if not self.sampled:
            return self._expect(program, axis, detector).mean
        with program.context as q:
            ops.MeasureHomodyne(axis.angle) | q[0]
        value = float(Engine("gaussian").run(program).samples[0, 0]) / SF_SCALE
        if detector.electronic_variance:
            value += np.random.normal(
                0.0, sqrt(detector.electronic_variance * VACUUM_VARIANCE)
            )
        return value

    @staticmethod
    def _expect(
        program: Program, axis: QuadratureAxis, detector: Detector
    ) -> Expectation:
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
        """Bob prepares S(s)D(alpha)|0> and sends it through the forward channel."""
        forward = self.noise.forward
        ops.Dgate(*polar(state.alpha)) | mode
        # Strawberry Fields' squeezing sign convention is opposite to the paper's.
        ops.Sgate(-state.squeeze_r, state.theta) | mode
        ops.ThermalLossChannel(forward.transmittance, forward.nbar) | mode


def make_backend(config: SimulatorConfig) -> Backend:
    if config.backend == "analytic":
        return AnalyticBackend()
    return StrawberryFieldsBackend(config.noise, sampled=config.backend == "sf-sampled")
