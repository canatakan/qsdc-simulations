"""Sampled Strawberry Fields backend with executable noise effects."""

from __future__ import annotations

from cmath import polar
from dataclasses import dataclass, field
from math import prod, sqrt

import numpy as np
from strawberryfields import Engine, Program, ops

from qsdc.common.quadrature import QuadratureAxis
from qsdc.protocols.srikara.configuration.noise import (
    ElectronicNoiseConfig,
    NoiseConfig,
)
from qsdc.protocols.srikara.simulator.backends.analytic.calculations import (
    displacement_after_unsqueeze,
)
from qsdc.protocols.srikara.simulator.backends.base import (
    MeasurementExpectation,
    QSDCBackend,
)
from qsdc.protocols.srikara.simulator.backends.strawberryfields.utils.calculations import (
    homodyne_sample,
    normalize_quadrature,
    normalize_quadrature_variance,
)
from qsdc.protocols.srikara.simulator.backends.strawberryfields.utils.noise import Noise
from qsdc.protocols.srikara.simulator.encoding import beta_for_message_value


@dataclass(frozen=True)
class SFNoiseBackend(QSDCBackend):
    """One-shot SF measurements with calibrated expectations."""

    noise: NoiseConfig = field(default_factory=NoiseConfig)
    name: str = "sf-noise"
    measurement_noise_sigma: float = 0.5

    def begin_run(self, seed: int) -> None:
        np.random.seed(seed)

    def control_measurement(
        self, alpha: complex, squeeze_r: float, theta: float, axis: QuadratureAxis
    ) -> float:
        program = self._control_program(alpha, squeeze_r, theta)
        measured = homodyne_sample(program, axis)
        return Noise.apply_electronic_noise(measured, self.noise.alice_readout)

    def returned_measurement(
        self,
        alpha: complex,
        squeeze_r: float,
        theta: float,
        beta: complex,
        axis: QuadratureAxis,
    ) -> float:
        program = self._returned_program(alpha, squeeze_r, theta, beta)
        measured = homodyne_sample(program, axis)
        return Noise.apply_electronic_noise(measured, self.noise.bob_readout)

    def message_response_factor(
        self, squeeze_r: float, theta: float, axis: QuadratureAxis
    ) -> float:
        ideal_response = displacement_after_unsqueeze(
            beta_for_message_value(1.0), squeeze_r, theta
        )
        component = axis.component(ideal_response)
        gain = prod(
            sqrt(effect.transmittance) for effect in self.noise.return_path
        )
        gain *= prod(
            sqrt(effect.efficiency) for effect in self.noise.bob_detector
        )
        return gain * component

    def control_expectation(
        self,
        alpha: complex,
        squeeze_r: float,
        theta: float,
        axis: QuadratureAxis,
    ) -> MeasurementExpectation:
        return self._expectation(
            self._control_program(alpha, squeeze_r, theta),
            axis,
            readout_effects=self.noise.alice_readout,
        )

    def returned_expectation(
        self,
        alpha: complex,
        squeeze_r: float,
        theta: float,
        axis: QuadratureAxis,
    ) -> MeasurementExpectation:
        return self._expectation(
            self._returned_program(alpha, squeeze_r, theta, beta=0j),
            axis,
            readout_effects=self.noise.bob_readout,
        )

    def _expectation(
        self,
        program: Program,
        axis: QuadratureAxis,
        readout_effects: list[ElectronicNoiseConfig],
    ) -> MeasurementExpectation:
        state = Engine("gaussian").run(program).state
        if state is None:
            raise RuntimeError("Strawberry Fields execution returned no state")

        mean, variance = state.quad_expectation(
            0,
            axis.angle,
        )
        mean = normalize_quadrature(float(mean))
        variance = normalize_quadrature_variance(float(variance))
        variance += sum(
            Noise.readout_variance(effect.variance_snu)
            for effect in readout_effects
        )
        return MeasurementExpectation(mean=mean, sigma=sqrt(variance))

    def _control_program(
        self,
        alpha: complex,
        squeeze_r: float,
        theta: float,
    ) -> Program:
        program = Program(1)
        alpha_abs, alpha_phase = polar(alpha)

        with program.context as q:
            ops.Dgate(alpha_abs, alpha_phase) | q[0]
            ops.Sgate(-squeeze_r, theta) | q[0]
            Noise.apply_channel_noise(q[0], self.noise.forward)
            ops.Sgate(squeeze_r, theta) | q[0]
            Noise.apply_detector_noise(q[0], self.noise.alice_detector)

        return program

    def _returned_program(
        self,
        alpha: complex,
        squeeze_r: float,
        theta: float,
        beta: complex,
    ) -> Program:
        program = Program(1)
        alpha_abs, alpha_phase = polar(alpha)
        beta_abs, beta_phase = polar(beta)

        with program.context as q:
            ops.Dgate(alpha_abs, alpha_phase) | q[0]
            ops.Sgate(-squeeze_r, theta) | q[0]
            Noise.apply_channel_noise(q[0], self.noise.forward)
            Noise.apply_delay(q[0], self.noise.alice_delay)
            ops.Dgate(beta_abs, beta_phase) | q[0]
            Noise.apply_channel_noise(q[0], self.noise.return_path)
            ops.Sgate(squeeze_r, theta) | q[0]
            Noise.apply_detector_noise(q[0], self.noise.bob_detector)

        return program
