"""Sampled Strawberry Fields backend with executable noise effects."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt

import numpy as np
import strawberryfields as sf
from strawberryfields import ops

from qsdc.protocols.srikara.simulator.backends.analytic.calculations import (
    displacement_after_unsqueeze,
)
from qsdc.protocols.srikara.simulator.backends.base import (
    MeasurementExpectation,
    QSDCBackend,
)
from qsdc.protocols.srikara.simulator.backends.strawberryfields.calculations import (
    homodyne_angle,
    homodyne_component_std,
    sf_gate_args,
)
from qsdc.protocols.srikara.simulator.encoding import beta_for_message_value
from qsdc.protocols.srikara.simulator.noise import NoiseModel


@dataclass(frozen=True)
class SFNoiseBackend(QSDCBackend):
    """One-shot SF measurements with calibrated expectations."""

    noise: NoiseModel = field(default_factory=NoiseModel)
    name: str = "sf-noise"
    measurement_noise_sigma: float = homodyne_component_std()

    def begin_run(self, seed: int) -> None:
        np.random.seed(seed)

    def control_measurement(
        self, alpha: complex, squeeze_r: float, theta: float, axis: str
    ) -> float:
        program = self._control_program(alpha, squeeze_r, theta)
        measured = _homodyne_sample(program, axis)
        return float(self.noise.apply("alice_readout", measured))

    def returned_measurement(
        self,
        alpha: complex,
        squeeze_r: float,
        theta: float,
        beta: complex,
        axis: str,
    ) -> float:
        program = self._returned_program(alpha, squeeze_r, theta, beta)
        measured = _homodyne_sample(program, axis)
        return float(self.noise.apply("bob_readout", measured))

    def message_response_factor(
        self, squeeze_r: float, theta: float, axis: str
    ) -> float:
        ideal_response = displacement_after_unsqueeze(
            beta_for_message_value(1.0), squeeze_r, theta
        )
        if axis == "q":
            component = ideal_response.real
        elif axis == "p":
            component = ideal_response.imag
        else:
            raise ValueError(f"unknown quadrature axis {axis!r}")
        return self.noise.amplitude_gain("return_path", "bob_detector") * component

    def control_expectation(
        self,
        alpha: complex,
        squeeze_r: float,
        theta: float,
        axis: str,
    ) -> MeasurementExpectation:
        return self._expectation(
            self._control_program(alpha, squeeze_r, theta),
            axis,
            readout_stage="alice_readout",
        )

    def returned_expectation(
        self,
        alpha: complex,
        squeeze_r: float,
        theta: float,
        axis: str,
    ) -> MeasurementExpectation:
        return self._expectation(
            self._returned_program(alpha, squeeze_r, theta, beta=0j),
            axis,
            readout_stage="bob_readout",
        )

    def _expectation(
        self,
        program: sf.Program,
        axis: str,
        readout_stage: str,
    ) -> MeasurementExpectation:
        state = sf.Engine("gaussian").run(program).state
        index = _quadrature_index(axis)
        mean = float(state.means()[index]) / 2.0
        variance = float(state.cov()[index, index]) / 4.0
        variance += sum(
            effect.variance for effect in self.noise.at(readout_stage)
        )
        return MeasurementExpectation(mean=mean, sigma=sqrt(variance))

    def _control_program(
        self,
        alpha: complex,
        squeeze_r: float,
        theta: float,
    ) -> sf.Program:
        program = sf.Program(1)
        alpha_abs, alpha_phase = sf_gate_args(alpha)

        with program.context as q:
            ops.Dgate(alpha_abs, alpha_phase) | q[0]
            ops.Sgate(-squeeze_r, theta) | q[0]
            self.noise.apply("forward", q[0])
            ops.Sgate(squeeze_r, theta) | q[0]
            self.noise.apply("alice_detector", q[0])

        return program

    def _returned_program(
        self,
        alpha: complex,
        squeeze_r: float,
        theta: float,
        beta: complex,
    ) -> sf.Program:
        program = sf.Program(1)
        alpha_abs, alpha_phase = sf_gate_args(alpha)
        beta_abs, beta_phase = sf_gate_args(beta)

        with program.context as q:
            ops.Dgate(alpha_abs, alpha_phase) | q[0]
            ops.Sgate(-squeeze_r, theta) | q[0]
            self.noise.apply("forward", q[0])
            self.noise.apply("alice_delay", q[0])
            if beta != 0:
                ops.Dgate(beta_abs, beta_phase) | q[0]
            self.noise.apply("return_path", q[0])
            ops.Sgate(squeeze_r, theta) | q[0]
            self.noise.apply("bob_detector", q[0])

        return program


def _homodyne_sample(program: sf.Program, axis: str) -> float:
    """Perform exactly one SF execution containing one homodyne measurement."""

    with program.context as q:
        ops.MeasureHomodyne(homodyne_angle(axis)) | q[0]
    result = sf.Engine("gaussian").run(program)
    return float(result.samples[0, 0]) / 2.0


def _quadrature_index(axis: str) -> int:
    if axis == "q":
        return 0
    if axis == "p":
        return 1
    raise ValueError(f"unknown quadrature axis {axis!r}")
