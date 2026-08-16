"""SF backend that samples homodyne measurements."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from qsdc.common.quadrature import QuadratureAxis
from qsdc.protocols.srikara.simulator.backends.base import QSDCBackend
from qsdc.protocols.srikara.simulator.backends.strawberryfields.utils.calculations import (
    build_program,
    homodyne_sample,
    quadrature_mean,
)
from qsdc.protocols.srikara.simulator.encoding import beta_for_message_value


@dataclass(frozen=True)
class SFSampledBackend(QSDCBackend):
    """SF Gaussian circuits with sampled homodyne readout."""

    name: str = "sf-sampled"
    measurement_noise_sigma: float = 0.5

    def begin_run(self, seed: int) -> None:
        np.random.seed(seed)

    def control_measurement(
        self, alpha: complex, squeeze_r: float, theta: float, axis: QuadratureAxis
    ) -> float:
        return homodyne_sample(
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
        return homodyne_sample(
            build_program(alpha, squeeze_r, theta, beta),
            axis,
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
