"""Formula-only backend for the paper's ideal algebra."""

from __future__ import annotations

from dataclasses import dataclass

from qsdc.protocols.srikara.simulator.backends.analytic.calculations import (
    displacement_after_unsqueeze,
)
from qsdc.protocols.srikara.simulator.backends.base import QSDCBackend
from qsdc.protocols.srikara.simulator.encoding import beta_for_message_value


@dataclass(frozen=True)
class AnalyticBackend(QSDCBackend):
    """Formula-only backend following the paper's ideal algebra."""

    name: str = "analytic"
    measurement_noise_sigma: float = 1e-7

    def begin_run(self, seed: int) -> None:
        pass

    def control_measurement(
        self, alpha: complex, squeeze_r: float, theta: float, axis: str
    ) -> float:
        if axis == "q":
            return alpha.real
        if axis == "p":
            return alpha.imag
        raise ValueError(f"unknown quadrature axis {axis!r}")

    def returned_measurement(
        self, alpha: complex, squeeze_r: float, theta: float, beta: complex, axis: str
    ) -> float:
        returned_alpha = alpha + displacement_after_unsqueeze(beta, squeeze_r, theta)
        if axis == "q":
            return returned_alpha.real
        if axis == "p":
            return returned_alpha.imag
        raise ValueError(f"unknown quadrature axis {axis!r}")

    def message_response_factor(
        self, squeeze_r: float, theta: float, axis: str
    ) -> float:
        response = displacement_after_unsqueeze(
            beta_for_message_value(1.0), squeeze_r, theta
        )
        if axis == "q":
            return response.real
        if axis == "p":
            return response.imag
        raise ValueError(f"unknown quadrature axis {axis!r}")
