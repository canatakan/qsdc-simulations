"""SF backend that samples homodyne measurements."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from qsdc.protocols.srikara.simulator.backends.base import QSDCBackend
from qsdc.protocols.srikara.simulator.backends.strawberryfields.calculations import (
    build_control_program,
    build_returned_program,
    homodyne_component_std,
    homodyne_sample,
    mean_component,
    message_unit_beta,
)
from qsdc.protocols.srikara.simulator.config import DEFAULT_SAMPLED_TOLERANCE_SIGMAS


@dataclass(frozen=True)
class SFSampledBackend(QSDCBackend):
    """SF Gaussian circuits with sampled homodyne readout."""

    name: str = "sf-sampled"
    default_tolerance_sigmas: float = DEFAULT_SAMPLED_TOLERANCE_SIGMAS
    measurement_noise_sigma: float = homodyne_component_std()

    def begin_run(self, seed: int) -> None:
        np.random.seed(seed)

    def control_measurement(
        self, alpha: complex, squeeze_r: float, theta: float, axis: str
    ) -> float:
        return homodyne_sample(build_control_program(alpha, squeeze_r, theta), axis)

    def returned_measurement(
        self, alpha: complex, squeeze_r: float, theta: float, beta: complex, axis: str
    ) -> float:
        return homodyne_sample(
            build_returned_program(alpha, squeeze_r, theta, beta),
            axis,
        )

    def message_response_factor(
        self, squeeze_r: float, theta: float, axis: str
    ) -> float:
        return mean_component(
            build_returned_program(
                alpha=0j,
                squeeze_r=squeeze_r,
                theta=theta,
                beta=message_unit_beta(),
            ),
            axis,
        )
