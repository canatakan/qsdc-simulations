"""Formula-only backend for the paper's ideal algebra."""

from __future__ import annotations

from dataclasses import dataclass

from qsdc.common.quadrature import QuadratureAxis
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
        self, alpha: complex, squeeze_r: float, theta: float, axis: QuadratureAxis
    ) -> float:
        return axis.component(alpha)

    def returned_measurement(
        self,
        alpha: complex,
        squeeze_r: float,
        theta: float,
        beta: complex,
        axis: QuadratureAxis,
    ) -> float:
        returned_alpha = alpha + displacement_after_unsqueeze(beta, squeeze_r, theta)
        return axis.component(returned_alpha)

    def message_response_factor(
        self, squeeze_r: float, theta: float, axis: QuadratureAxis
    ) -> float:
        response = displacement_after_unsqueeze(
            beta_for_message_value(1.0), squeeze_r, theta
        )
        return axis.component(response)
