"""SF backend that reads ideal Gaussian state means."""

from __future__ import annotations

from dataclasses import dataclass

from qsdc.common.quadrature import QuadratureAxis
from qsdc.protocols.srikara.simulator.backends.base import QSDCBackend
from qsdc.protocols.srikara.simulator.backends.strawberryfields.utils.calculations import (
    build_program,
    quadrature_mean,
)
from qsdc.protocols.srikara.simulator.encoding import beta_for_message_value


@dataclass(frozen=True)
class SFBackend(QSDCBackend):
    """SF Gaussian circuits with exact state-mean readout."""

    name: str = "sf"
    measurement_noise_sigma: float = 1e-7

    def begin_run(self, seed: int) -> None:
        pass

    def control_measurement(
        self, alpha: complex, squeeze_r: float, theta: float, axis: QuadratureAxis
    ) -> float:
        return quadrature_mean(
            build_program(alpha, squeeze_r, theta, beta=0j),
            axis,
        )

    def returned_measurement(
        self,
        alpha: complex,
        squeeze_r: float,
        theta: float,
        beta: complex,
        axis: QuadratureAxis,
    ) -> float:
        return quadrature_mean(
            build_program(alpha, squeeze_r, theta, beta), axis
        )

    def message_response_factor(
        self, squeeze_r: float, theta: float, axis: QuadratureAxis
    ) -> float:
        return quadrature_mean(
            build_program(
                alpha=0j,
                squeeze_r=squeeze_r,
                theta=theta,
                beta=beta_for_message_value(1.0),
            ),
            axis,
        )
