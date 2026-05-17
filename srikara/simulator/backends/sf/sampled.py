"""SF backend that samples homodyne measurements."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from srikara.simulator.core.config import (
    DEFAULT_SAMPLED_REPETITIONS,
    DEFAULT_SAMPLED_TOLERANCE_SIGMAS,
    validate_sampled_repetitions,
)
from ..base import QSDCBackend
from .calculations import (
    build_control_program,
    build_returned_program,
    homodyne_component_std,
    homodyne_mean,
    mean_component,
    message_unit_beta,
)


@dataclass(frozen=True)
class SFSampledBackend(QSDCBackend):
    """SF Gaussian circuits with sampled homodyne readout."""

    name: str = "sf-sampled"
    repetitions: int = DEFAULT_SAMPLED_REPETITIONS
    homodyne_tolerance_sigmas: float = DEFAULT_SAMPLED_TOLERANCE_SIGMAS

    @property
    def default_tolerance(self) -> float:
        validate_sampled_repetitions(self.repetitions)
        return (
            self.homodyne_tolerance_sigmas
            * homodyne_component_std()
            / np.sqrt(self.repetitions)
        )

    def begin_run(self, seed: int) -> None:
        np.random.seed(seed)

    def control_measurement(
        self, alpha: complex, squeeze_r: float, theta: float, axis: str
    ) -> float:
        return homodyne_mean(
            build_control_program, (alpha, squeeze_r, theta), axis, self.repetitions
        )

    def returned_measurement(
        self, alpha: complex, squeeze_r: float, theta: float, beta: complex, axis: str
    ) -> float:
        return homodyne_mean(
            build_returned_program,
            (alpha, squeeze_r, theta, beta),
            axis,
            self.repetitions,
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
